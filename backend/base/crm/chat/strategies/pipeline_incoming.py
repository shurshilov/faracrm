# Copyright 2025 FARA CRM
# Chat module - incoming message pipeline
#
# Оркестрация ВХОДЯЩЕГО сообщения, вынесенная из ChatStrategyBase.
#
# Разделение ответственности:
#   • стратегия (strategy.py) — ТРАНСПОРТ провайдера: парсинг (адаптер),
#     скачивание файлов, item-info, отправка. Она же держит эти хуки.
#   • пайплайн (этот модуль) — СЦЕНАРИЙ: «куда лечь сообщению, кто автор,
#     нужен ли лид, что ушло по WS». Один короткий проход из маленьких шагов
#     над общим контекстом IncomingMessage: resolve → route → lead → persist
#     → notify.
#   • домен лида (leads.create_or_get_for_chat) — ПРАВИЛА ЛИДА.
#
# Свою транзакцию пайплайн НЕ открывает: и handle_webhook, и email-крон
# (cron_fetch_emails) уже оборачивают вызов в
# транзакцию.

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
import json
import logging

from backend.base.crm.users.models.users import SYSTEM_USER_ID

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.partners.models.contact import Contact
    from backend.project_setup import ChatConnector
    from backend.base.crm.chat.models.chat_message import ChatMessage
    from backend.base.crm.chat.models.chat import Chat
    from backend.base.crm.chat.models.chat_external_chat import (
        ChatExternalChat,
    )
    from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter
    from backend.base.crm.chat.strategies.strategy import ChatStrategyBase

logger = logging.getLogger(__name__)


class IncomingRoute(str, Enum):
    """
    Судьба входящего сообщения — ВСЕ возможные исходы, по одному имени на исход.

    Порядок принятия решения: ПЕРЕПИСКА → СВЯЗЬ → ХОЛОДНЫЙ СТАРТ.
    Он важен: только переписка различает два наших чата с одним адресатом
    (личный и групповой) — адрес у них общий. Не менять местами.
    """

    # Адрес/тред уже привязан к чату (chat_external_chat). Основной путь.
    ROUTED_BY_LINK = "routed_by_link"

    # Сообщение само сказало, куда лечь: «я ответ вон на те». Только email.
    ROUTED_BY_THREAD = "routed_by_thread"

    # Переписки нет, контакта раньше не было → завели партнёра и его чат.
    ROUTED_PARTNER_NEW = "routed_partner_new"

    # Переписки нет, но партнёр уже известен → открыли/нашли его чат.
    ROUTED_PARTNER_KNOWN = "routed_partner_known"

    # Наш сотрудник написал на общий адрес, переписки с ним ещё нет.
    SKIP_OWN_USER = "skip_own_user"

    # Контакт есть, но у него не заполнен ни партнёр, ни пользователь.
    SKIP_ERROR_NO_PARTNER_NO_USER = "skip_error_no_partner_no_user"

    # Не поняли, КТО ИЗ ДВОИХ клиент: resolve_partner вернул (None, None).
    SKIP_ERROR_COUNTERPARTY = "skip_error_counterparty"


# Исходы, при которых чата нет и обрабатывать нечего.
_SKIP_ROUTES = frozenset(
    {
        IncomingRoute.SKIP_ERROR_COUNTERPARTY,
        IncomingRoute.SKIP_OWN_USER,
        IncomingRoute.SKIP_ERROR_NO_PARTNER_NO_USER,
    }
)


@dataclass
class IncomingMessage:
    """Контекст обработки одного входящего сообщения — заполняется по шагам.

    Входы (env/connector/adapter/strategy) приходят в конструктор. Поля, которые
    задаются ШАГАМИ пайплайна (contact, route, chat_id, message,
    counterparty_external_id), помечены field(init=False): они НЕ параметры
    конструктора и объявлены НЕ-Optional — чтобы не тащить `| None` в каждый
    доступ. К моменту чтения значение уже задано своим шагом; обращение раньше
    времени → AttributeError (громкий баг порядка шагов, а не тихий None, и без
    `# type: ignore`). Поля, которые РЕАЛЬНО могут остаться None (external_chat,
    lead_id, author_*), — честный Optional.

    NB про chat_id: у skip-исходов чата нет, а _log_route читает его на любом
    исходе → даём default=0 и логируем как None (см. ниже).
    """

    env: "Environment"
    connector: "ChatConnector"
    adapter: "ChatMessageAdapter"
    strategy: "ChatStrategyBase"

    # не обязательные
    counterparty_external_name: str | None = None
    created: bool = False
    counterparty_name: str | None = None
    external_chat: "ChatExternalChat | None" = None
    lead_id: int | None = None
    author_user_id: int | None = None
    author_partner_id: int | None = None
    attachments_payload: list = field(default_factory=list)

    # обязательные но заполняются постепенно
    chat: "Chat" = field(init=False)
    chat_id: int = field(init=False)
    counterparty_external_id: str = field(init=False)
    contact: "Contact" = field(init=False)
    route: "IncomingRoute" = field(init=False)
    message: "ChatMessage" = field(init=False)


class IncomingMessagePipeline:
    """Прогоняет одно входящее сообщение по шагам. См. docstring модуля.

    Транспортные хуки зовём через ctx.strategy, поэтому переопределения в
    конкретных стратегиях (Avito.resolve_partner_id_and_name, get_item_info
    и т.п.) работают как раньше — диспетчеризация по переданному экземпляру.
    """

    def __init__(
        self,
        strategy,
        env,
        connector,
        adapter,
        notify=True,
        generate_lead=True,
    ):
        self.ctx = IncomingMessage(
            env=env, connector=connector, adapter=adapter, strategy=strategy
        )
        # режим истории, когда не создается новое, а берется
        # старое событие, например CDR история звонков
        # тогда нет смысла генерировать лиды и слать попап по ws
        self.notify = notify
        self.generate_lead = generate_lead

    async def run(self) -> None:
        ctx = self.ctx
        if not await self._resolve_counterparty():
            return
        await self._resolve_contact()
        await self._route_to_chat()
        self._log_route()
        if ctx.route in _SKIP_ROUTES:
            return
        if self.generate_lead:
            await self._attach_lead()
        await self._persist_message()
        if self.notify:
            await self._notify()

    async def _resolve_counterparty(self) -> bool:
        """Клиент-контрагент: его внешние id и имя одним хуком стратегии.

        Обычно это автор сообщения; в Avito webhook приходит и на наши
        исходящие — там стратегия вычисляет клиента по участникам чата, а не
        по author_id (это был бы наш аккаунт). Пусто → не поняли, кто клиент:
        пропускаем, чтобы не завести партнёра/лид на наш собственный аккаунт.
        """
        ctx = self.ctx
        ext_id, ext_name = await ctx.strategy.resolve_partner_id_and_name(
            ctx.connector, ctx.adapter
        )
        if not ext_id:
            logger.info(
                "[%s] Message %s → %s",
                ctx.strategy.strategy_type,
                ctx.adapter.message_id,
                IncomingRoute.SKIP_ERROR_COUNTERPARTY.value,
            )
            return False
        ctx.counterparty_external_id = ext_id
        ctx.counterparty_external_name = ext_name
        return True

    async def _resolve_contact(self) -> None:
        """Контакт клиента (+ партнёр, если адрес незнакомый) и его имя.

        Контакт полиморфен — имя берём у того владельца, который есть.
        external_chat находим здесь и безусловно: он нужен и маршрутизации, и
        лидогенерации. По external_id ЛИБО address (write-first мог создать
        связь по номеру).
        """
        ctx = self.ctx
        _, ctx.contact, ctx.created = (
            await ctx.env.models.chat_external_account.find_or_create_for_webhook(
                connector=ctx.connector,
                external_id=ctx.counterparty_external_id,
                contact_value=ctx.counterparty_external_id,
                display_name=ctx.counterparty_external_name,
                raw=json.dumps(ctx.adapter.raw) if ctx.adapter.raw else None,
            )
        )

        contact = ctx.contact
        if contact.partner_id:
            ctx.counterparty_name = contact.partner_id.name
        elif contact.user_id:
            ctx.counterparty_name = contact.user_id.name

        ctx.external_chat = (
            await ctx.env.models.chat_external_chat.find_by_id_or_address(
                key=ctx.adapter.chat_id,
                connector_id=ctx.connector.id,
            )
        )

    async def _route_to_chat(self) -> None:
        """Куда класть сообщение: ПЕРЕПИСКА → СВЯЗЬ → ХОЛОДНЫЙ СТАРТ.

        Цепочка резолверов: первый, кто может определить чат, забирает
        сообщение (ставит route + chat_id). Порядок важен — только переписка
        различает два наших чата с одним адресатом. Ни один не забрал —
        класть некуда: skip-исход по наличию user (см. IncomingRoute).
        """
        ctx = self.ctx
        for resolver in (
            self._route_by_thread,
            self._route_by_link,
            self._route_by_cold_start,
        ):
            if await resolver():
                return
        ctx.route = (
            IncomingRoute.SKIP_OWN_USER
            if ctx.contact.user_id
            else IncomingRoute.SKIP_ERROR_NO_PARTNER_NO_USER
        )

    async def _route_by_thread(self) -> bool:
        """Переписка: сообщение само сказало «я ответ вон на те». Только email —
        у прочих адаптеров thread_message_ids пуст по дефолту."""
        ctx = self.ctx
        if not ctx.adapter.thread_message_ids:
            return False
        chat = await ctx.env.models.chat_external_message.thread_incoming_chat(
            external_ids=ctx.adapter.thread_message_ids,
            connector_id=ctx.connector.id,
        )
        if not chat:
            return False

        ctx.chat = chat
        ctx.chat_id = chat.id
        ctx.route = IncomingRoute.ROUTED_BY_THREAD
        return True

    async def _route_by_link(self) -> bool:
        """Связь: тред уже привязан к чату (chat_external_chat.chat_id)."""
        ctx = self.ctx
        if not (ctx.external_chat and ctx.external_chat.chat_id):
            return False
        ctx.chat = ctx.external_chat.chat_id
        ctx.chat_id = ctx.chat.id
        ctx.route = IncomingRoute.ROUTED_BY_LINK
        return True

    async def _route_by_cold_start(self) -> bool:
        """Холодный старт с клиентом: его единственный внешний чат (модель 1:1),
        и сразу привязываем к нему тред."""
        ctx = self.ctx
        if not ctx.contact.partner_id:
            return False
        chat = await ctx.env.models.chat.get_or_create_partner_chat(
            ctx.contact.partner_id.id,
            connector=ctx.connector,
            partner_name=ctx.counterparty_name,
        )
        ctx.chat = chat
        ctx.chat_id = chat.id
        ctx.route = (
            IncomingRoute.ROUTED_PARTNER_NEW
            if ctx.created
            else IncomingRoute.ROUTED_PARTNER_KNOWN
        )
        item_title, item_url = await ctx.strategy._fetch_item_info(
            ctx.connector, ctx.adapter
        )
        await ctx.env.models.chat_external_chat.create_link(
            external_id=ctx.adapter.chat_id,
            connector_id=ctx.connector.id,
            chat_id=ctx.chat_id,
            item_title=item_title,
            item_url=item_url,
        )
        ctx.external_chat = (
            await ctx.env.models.chat_external_chat.find_by_external_id(
                external_id=ctx.adapter.chat_id,
                connector_id=ctx.connector.id,
            )
        )
        return True

    def _log_route(self) -> None:
        """Одна строка на исход — по ней видно судьбу ЛЮБОГО сообщения."""
        ctx = self.ctx
        logger.info(
            "[%s] Message %s → %s (chat=%s, contact=%s)",
            ctx.strategy.strategy_type,
            ctx.adapter.message_id,
            ctx.route.value,
            ctx.chat_id,
            ctx.contact.id,
        )

    async def _attach_lead(self) -> None:
        """Лидогенерация — ДО создания сообщения, чтобы сразу проставить
        message.lead_id (тег «ленты»).

        Лид резолвится по клиенту-контрагенту; при исходящем автор — оператор,
        но лид всё равно на клиента (contact.partner_id). Сбой не валит
        обработку: lead_id=None, сообщение остаётся видно в партнёр-скоупе
        ленты. Сами правила (дедуп по website, имя, назначение) — в домене
        лида: lead.create_or_get_for_chat.
        """
        ctx = self.ctx
        if not ctx.connector.lead_generation or not ctx.contact.partner_id:
            return
        try:
            item_title = ""
            item_url = ""
            if ctx.external_chat:
                item_title = (ctx.external_chat.item_title or "").strip()
                item_url = (ctx.external_chat.item_url or "").strip()
            lead = await ctx.env.models.lead.create_or_get_for_chat(
                connector=ctx.connector,
                partner=ctx.contact.partner_id,
                item_title=item_title,
                item_url=item_url,
                message_text=ctx.adapter.text or "",
                author_name=ctx.adapter.author_name or "",
                source_message_id=ctx.adapter.message_id,
            )
            if lead is not None:
                ctx.lead_id = lead.id
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] Lead generation failed for message %s: %s",
                ctx.strategy.strategy_type,
                ctx.adapter.message_id,
                exc,
                exc_info=True,
            )

    async def _persist_message(self) -> None:
        """Создаём сообщение, связь с внешним и вложения.

        Тело для хранения — adapter.serialized_body (email упаковывает
        {subject,html} в JSON; прочие отдают текст). Канал несёт
        connector_type (проставляется в post_message из connector.type).
        Вложения возвращаются уже в форме REST /messages — кладём их в WS ниже,
        чтобы бинарный контент показывался вживую, без F5.
        """
        ctx = self.ctx
        # мягко удалённый чат не должен молча принимать входящее: если тред лёг
        # в удалённый чат, возвращаем его к жизни иначе оператор не увидит

        await ctx.chat.reactivate()
        ctx.author_user_id, ctx.author_partner_id = self._resolve_author()
        message = await ctx.env.models.chat_message.post_message(
            chat_id=ctx.chat_id,
            author_user_id=ctx.author_user_id,
            author_partner_id=ctx.author_partner_id,
            body=ctx.adapter.serialized_body,
            connector_id=ctx.connector.id,
            lead_id=ctx.lead_id,
        )
        ctx.message = message
        await ctx.env.models.chat_external_message.create_link(
            external_id=ctx.adapter.message_id,
            connector_id=ctx.connector.id,
            message_id=message.id,
            external_chat_id=ctx.adapter.chat_id,
        )
        ctx.attachments_payload = await ctx.strategy.save_attachments(
            ctx.connector, ctx.adapter, message
        )

    def _resolve_author(self) -> tuple[int | None, int | None]:
        """Автор сообщения. contact — контакт КЛИЕНТА-контрагента.

        Входящее от клиента → автор клиент (или оператор, если контакт
        привязан к user). Наше исходящее (например, оператор написал клиенту
        прямо из приложения Avito) — конкретного оператора webhook не даёт,
        поэтому автор системный пользователь («магазин»).
        """
        ctx = self.ctx
        if ctx.adapter.is_from_external:
            if ctx.contact.user_id:
                return ctx.contact.user_id.id, None
            if ctx.contact.partner_id:
                return None, ctx.contact.partner_id.id
            return None, None
        return SYSTEM_USER_ID, None

    async def _notify(self) -> None:
        """WS-уведомление о новом сообщении.

        partner_id/lead_id едут в пейлоаде тегами «ленты» — по ним фронт роутит
        событие в ленты партнёра/лида (помимо кэша чата). partner_id тут
        известен даром (contact.partner_id), поэтому кладём оба тега.
        """
        ctx = self.ctx
        author_data = {
            "id": ctx.author_user_id or ctx.author_partner_id,
            "name": ctx.counterparty_name or ctx.adapter.author_name,
            "type": "user" if ctx.author_user_id else "partner",
        }
        payload = ctx.message.serialize_for_ws(
            author=author_data,
            attachments=ctx.attachments_payload,
            connector_type=ctx.connector.type,
            author_user_id=ctx.author_user_id,
            author_partner_id=ctx.author_partner_id,
            partner_id=(
                ctx.contact.partner_id.id if ctx.contact.partner_id else None
            ),
            lead_id=ctx.lead_id,
            body_limit=200,
        )
        await ctx.env.apps.chat.chat_manager.send_to_chat(
            chat_id=ctx.chat_id,
            message={
                "type": "new_message",
                "chat_id": ctx.chat_id,
                "message": payload,
                "external": True,
            },
        )
        logger.info(
            "[%s] Processed message %s -> internal %s",
            ctx.strategy.strategy_type,
            ctx.adapter.message_id,
            ctx.message.id,
        )
