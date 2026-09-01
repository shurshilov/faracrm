from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.company.models.company import Company
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from backend.project_setup import ChatConnector
    from .team_crm import TeamCrm
    from .lead_stage import LeadStage

import logging

from ...partners.models.contact import Contact
from backend.base.system.dotorm.dotorm.decorators import depends, hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    One2many,
    Selection,
    Text,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.crm.users.audit_mixin import AuditMixin
from backend.base.system.core.enviroment import env
from backend.base.crm.security.polymorphic_parent import (
    PolymorphicParentMixin,
)

logger = logging.getLogger(__name__)


async def _stage_progress(stage) -> int:
    """Процент прохождения воронки по стадии (0–100).

    Отдельного «процента» у стадии нет: её вес — это sequence, а 100 %
    соответствует последней активной стадии. Так шкала подстраивается под
    любой набор стадий, включая пользовательские. Лид без стадии — 0 %.
    """
    if stage is None:
        return 0

    sequence = int(getattr(stage, "sequence", 0) or 0)
    if sequence <= 0:
        return 0

    last = await env.models.lead_stage.search(
        filter=[("active", "=", True)],
        fields=["sequence"],
        sort="sequence",
        order="DESC",
        limit=1,
    )
    top = int(last[0].sequence or 0) if last else 0
    return min(100, round(sequence * 100 / top)) if top > 0 else 0


class Lead(AuditMixin, PolymorphicParentMixin):
    __table__ = "leads"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Lead Name")
    active: bool = Boolean(default=True)
    stage_id: "LeadStage" = Many2one(
        lambda: env.models.lead_stage,
        string="Stage",
        index=True,
        ondelete="restrict",
    )
    user_id: "User | None" = Many2one(
        lambda: env.models.user,
        string="Salesperson",
        # index=True,
        ondelete="restrict",
    )
    partner_id: "Partner | None" = Many2one(
        lambda: env.models.partner,
        string="Partner",
        index=True,
        ondelete="restrict",
    )
    company_id: "Company | None" = Many2one(
        lambda: env.models.company, string="Company"
    )
    notes: str | None = Text(string="Notes")
    type: str = Selection(
        options=[
            ("lead", "Lead"),
            ("opportunity", "Opportunity"),
        ],
        default="lead",
        string="Type",
    )

    connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        string="Connector",
        ondelete="set null",
        description="Коннектор, через который создан лид",
    )

    # Команда лида. Раньше strategy._get_or_create_lead писал team_id из
    # правила маршрутизации, но поля не было → значение молча терялось.
    # Добавлено как реальное поле (правило маршрутизации теперь работает).
    team_id: "TeamCrm | None" = Many2one(
        relation_table=lambda: env.models.team_crm,
        string="Team",
        ondelete="set null",
        index=True,
        description="Команда, ответственная за лид",
    )

    website: str | None = Char(
        max_length=500,
        string="Website URL",
        description="URL объявления / контекста лида",
    )

    # Контакты (телефоны, email, telegram и т.д.)
    # Внешние аккаунты доступны через contact_ids.external_account_ids
    contact_ids: list["Contact"] = One2many(
        store=False,
        relation_table=lambda: env.models.contact,
        relation_table_field="partner_id",
        description="Контакты",
    )

    # Прогресс по воронке (0–100 %) — вычисляется из стадии.
    progress: int = Integer(
        string="Progress %",
        default=0,
        compute="_compute_progress",
    )

    @depends(triggers=[stage_id], prefetch=[(stage_id, "sequence")])
    async def _compute_progress(self) -> None:
        """Прогресс лида по стадии воронки.

        stage_id со свежим sequence уже подгружен движком @depends
        (prefetch), так что внутри остаётся только нормировка.
        Пересчитывается и в форме: stage_id — триггер @depends, поэтому
        попадает в get_onchange_fields() и уезжает в POST /onchange.
        """
        self.progress = await _stage_progress(self.stage_id)

    @hybridmethod
    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        """Pull-модель: когда лид «берут» (появляется user_id), ответственный
        автоматически подписывается на внешний чат клиента по этому коннектору.

        Лид создаётся без user_id и лежит в общем пуле; первый, кто поставит
        себя в Salesperson, становится участником чата и может писать клиенту.
        Старых участников не трогаем — история переписки видна всем, кто был
        в чате.
        """
        result = await super().update(payload, fields, session, depends_jobs)

        # Только когда проставляют ответственного.
        if fields is not None and "user_id" not in fields:
            return result
        if not payload.user_id or not self.partner_id or not self.connector_id:
            return result

        # Чаты клиента по этому коннектору: партнёр — активный участник, и
        # чат привязан к внешнему чату коннектора. Подписываем ответственного
        # (_ensure_membership добавит, только если ещё не участник).
        try:
            partner_members = await env.models.chat_member.search(
                filter=[
                    ("partner_id", "=", self.partner_id.id),
                    ("is_active", "=", True),
                ],
                fields=["chat_id"],
            )
            chat_ids = [m.chat_id.id for m in partner_members if m.chat_id]
            if chat_ids:
                ext_chats = await env.models.chat_external_chat.search(
                    filter=[
                        ("connector_id", "=", self.connector_id.id),
                        ("chat_id", "in", chat_ids),
                    ],
                    fields=["chat_id"],
                )
                for ec in ext_chats:
                    await env.models.chat(id=ec.chat_id.id)._ensure_membership(
                        ec.chat_id.id, payload.user_id.id
                    )
                    # _ensure_membership добавляет DB-участника, но НЕ
                    # подписывает live WS-сессию ответственного и не шлёт ему
                    # chat_created → без этого диалог всплывает у него только
                    # после рефреша. notify_new_chat (cross-worker через
                    # pubsub) подписывает его WS на любом воркере и уведомляет
                    # фронт. Best-effort: сбой не должен ломать обновление лида.
                    try:
                        await env.apps.chat.chat_manager.notify_new_chat(
                            payload.user_id.id, ec.chat_id.id
                        )
                    except Exception as notify_exc:  # noqa: BLE001
                        logger.warning(
                            "Lead %s: notify_new_chat failed for chat %s: %s",
                            self.id,
                            ec.chat_id.id,
                            notify_exc,
                        )
        except Exception as exc:  # noqa: BLE001
            # Подписка не должна ломать обновление лида.
            logger.warning(
                "Lead %s: failed to subscribe user to chat: %s", self.id, exc
            )
        return result

    @classmethod
    async def find_last_for_chat(cls, partner_id: int, connector_id: int):
        """
        Самый свежий лид клиента по этому коннектору.

        Один запрос на двоих: лидогенерация ищет, к чему прицепиться, а карточка
        звонка — куда вести оператора по ссылке. Правило «свежий лид клиента по
        каналу» должно быть в одном месте.
        """
        rows = await env.models.lead.search(
            filter=[
                ("partner_id", "=", partner_id),
                ("connector_id", "=", connector_id),
            ],
            fields=["id", "website", "name"],
            sort="id",
            order="DESC",
            limit=1,
        )
        return rows[0] if rows else None

    @hybridmethod
    async def create_or_get_for_chat(
        self,
        *,
        connector: "ChatConnector",
        partner: "Partner",
        item_title: str = "",
        item_url: str = "",
        message_text: str = "",
        author_name: str = "",
        source_message_id: str = "",
    ):
        """Найти переиспользуемый или создать лид из входящего сообщения чата.

        Раньше эта логика жила в ChatStrategyBase._get_or_create_lead — но
        правило «другой website ⇒ другой лид», выбор имени лида и применение
        правил маршрутизации (chat_routing_rule_lead) — это про лиды, а не про
        транспорт чата. Пайплайн входящего теперь зовёт этот фабричный метод
        (см. chat/strategies/incoming.py).

        Логика:
        - имя лида = item_title (заголовок объявления) или имя партнёра;
        - ищем существующий лид по (partner_id, connector_id), самый свежий;
        - если у найденного другой website (item_url) — клиент пишет по другому
          объявлению, это другой лид, создаём новый;
        - применяем правила chat_routing_rule_lead, если включено
          connector.lead_distribution.

        Возвращает запись лида (существующую или новую) либо None, если
        партнёр-клиент не задан (без него создавать лид бессмысленно).
        """
        if not partner:
            return None

        # partner может быть "stub" (только id) — но .name сюда уже приходит
        # загруженным из пайплайна; используем как раньше _get_or_create_lead.
        partner_name = partner.name

        item_title = (item_title or "").strip()
        item_url = (item_url or "").strip()

        # Ищем существующий лид по (partner_id, connector_id) — берём свежий.
        existing_lead = await self.find_last_for_chat(partner.id, connector.id)

        # Другой website — это другой лид.
        if (
            existing_lead
            and item_url
            and existing_lead.website
            and existing_lead.website != item_url
        ):
            existing_lead = None

        if existing_lead:
            # Обновим website, если он появился/сменился позже.
            if item_url and existing_lead.website != item_url:
                await existing_lead.update(env.models.lead(website=item_url))
            return existing_lead

        # Имя лида: заголовок объявления или имя партнёра.
        fallback_name = (
            partner_name
            or author_name
            or f"Lead {connector.name or connector.type}"
        )
        lead_name = item_title or fallback_name

        # Правила маршрутизации (назначение менеджера/команды).
        assigned_user = None
        assigned_team = None
        if connector.lead_distribution:
            try:
                # Структура payload (item_title, message_text, item_url,
                # partner_name) — общая для всех каналов, чтобы админ применял
                # одни и те же правила между системами.
                routing_payload = {
                    "item_title": item_title or "",
                    "message_text": message_text or "",
                    "item_url": item_url or "",
                    "partner_name": partner_name or author_name or "",
                }
                rule_user, rule = (
                    await env.models.chat_routing_rule_lead.find_user_for(
                        connector.id,
                        routing_payload,
                    )
                )
                if rule_user:
                    assigned_user = rule_user
                    if rule and rule.team_id:
                        assigned_team = rule.team_id
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Routing rule evaluation failed for connector %s: %s",
                    connector.id,
                    exc,
                )

        lead_payload = {
            "name": lead_name,
            "type": connector.lead_type or "opportunity",
            "partner_id": partner,
            "connector_id": env.models.chat_connector(id=connector.id),
            "website": item_url or None,
            "notes": (
                f"Создан из сообщения {source_message_id} ({connector.name})"
            ),
        }
        if assigned_user:
            lead_payload["user_id"] = assigned_user
        if assigned_team:
            lead_payload["team_id"] = assigned_team
        if connector.lead_stage_id:
            lead_payload["stage_id"] = connector.lead_stage_id

        new_lead = env.models.lead(**lead_payload)
        new_lead.id = await self.create(payload=new_lead)
        logger.info(
            "Created lead %s (name=%r) for partner %s via connector %s (%s)",
            new_lead.id,
            lead_name,
            partner.id,
            connector.id,
            connector.type,
        )
        return new_lead
