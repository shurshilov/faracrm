# Copyright 2025 FARA CRM
# Chat Phone module - abstract phone strategy

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Tuple

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.project_setup import ChatConnector
    from backend.base.crm.partners.models.contact import Contact
    from .adapter import PhoneMessageAdapter

logger = logging.getLogger(__name__)

# Лидогенерация при импорте истории. Карточку импорт не трогает НИКОГДА:
# у исторических записей событие всегда «завершён», то есть карточка умела бы
# только гаснуть — и погасила бы попап текущего разговора с тем же номером.
LEAD_ON_IMPORT = {"normal": True, "no_notify": True, "silent": False}


class PhoneStrategyBase(ChatStrategyBase):
    """
    АБСТРАКТНАЯ стратегия телефонного коннектора: только контракт провайдера.

    Стратегия — ТРАНСПОРТ: разобрать формат провайдера и сходить в его API.
    Решения по событию звонка (карточка, запись в реестр) принимает
    IncomingCallPipeline, реестр номеров ведёт модель PhoneNumber, фоновые
    задачи — chat_phone/cron.py.

    Конкретные стратегии: AsteriskPhoneStrategy (эталон, проверен в бою),
    SipuniPhoneStrategy, MegafonPhoneStrategy.
    """

    # Запись звонка качаем сами (content).
    attachments_source = "content"

    # Окно бэкофилла истории для cron: [now-WAIT-WINDOW, now-WAIT]. WAIT — фора
    # провайдеру на запись звонка в свою историю.
    HISTORY_WINDOW_MINUTES = 60
    HISTORY_WAIT_MINUTES = 1

    # ==================== контракт провайдера ====================

    async def fetch_numbers(self, connector: "ChatConnector") -> list[dict]:
        """
        Линии провайдера в УНИФИЦИРОВАННОМ виде (по одной на запись):

            {
              "external_id": "SIP/301",     # ключ upsert-а (с connector_id)
              "kind": "number",             # number / trunk / group / queue
              "number": "301",              # набираемый номер / линия
              "extension": "301",           # внутренний номер
              "name": "Отдел продаж",       # человекочитаемое имя
              "user_key": "301",            # чем искать контакт сотрудника
              "raw": {...},                 # сырая запись провайдера
            }
        """
        raise NotImplementedError(
            f"fetch_numbers not implemented for {self.strategy_type}"
        )

    async def fetch_call_history(
        self,
        connector: "ChatConnector",
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """
        История звонков за окно [start_date, end_date] (tz-aware datetime;
        формат под API выбирает провайдер). Записи — в том же виде, что и
        webhook-события: их разбирает тот же адаптер.
        """
        raise NotImplementedError(
            f"fetch_call_history not implemented for {self.strategy_type}"
        )

    async def final_call_records(
        self,
        connector: "ChatConnector",
        env: "Environment",
        adapter: "PhoneMessageAdapter",
    ) -> list[dict] | None:
        """
        Записи с полными данными звонка для завершающего события; None —
        событие самодостаточно (обычный случай). Asterisk переопределяет:
        ARI-хэнгап данных о звонке не несёт, они лежат в CDR.
        """
        return None

    async def log_event(
        self,
        connector: "ChatConnector",
        env: "Environment",
        adapter: "PhoneMessageAdapter",
    ) -> None:
        """
        Журнал событий провайдера. По умолчанию молчим; Asterisk пишет
        ARI-события в свой журнал телефонии (экран «События»).
        """
        return None

    async def _download_call_record(
        self,
        connector: "ChatConnector",
        adapter: "PhoneMessageAdapter",
    ) -> bytes | None:
        """Скачать запись разговора. По умолчанию — HTTP GET по call_record_url.
        Провайдеры переопределяют (напр. запрос к API по filename)."""
        url = adapter.call_record_url
        if not url:
            return None
        content, _mimetype = await self.file_download(connector, url)
        return content

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
        attachments: list | None = None,
    ) -> Tuple[str, str]:
        """Инициация исходящего звонка — по умолчанию не поддерживается."""
        raise NotImplementedError(
            f"Outgoing calls not supported for {self.strategy_type}"
        )

    # ==================== точки входа ====================

    async def _run_call_pipeline(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
        notify_card: bool = True,
        generate_lead: bool = True,
    ) -> None:
        """Одно событие звонка → пайплайн. Исключения НЕ глушим — они нужны
        импорту, чтобы честно посчитать неудачные записи."""
        adapter: "PhoneMessageAdapter" = self.create_message_adapter(
            connector, payload
        )  # type: ignore
        if adapter.should_skip:
            return

        from .pipeline_incoming_call import IncomingCallPipeline

        await IncomingCallPipeline(
            self,
            env,
            connector,
            adapter,
            notify_card=notify_card,
            generate_lead=generate_lead,
        ).run()

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
        notify: bool = True,
        generate_lead: bool = True,
    ) -> Any:
        """Событие звонка от провайдера → пайплайн (он и решает, что делать)."""
        try:
            await self._run_call_pipeline(
                connector, payload, env, notify, generate_lead
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                "[%s] phone webhook error: %s",
                self.strategy_type,
                e,
                exc_info=True,
            )
        # Провайдеру всегда 200: иначе он уйдёт в ретраи по нашей внутренней
        # ошибке, а событие звонка повторить всё равно нечем.
        return {"ok": True}

    async def test_connection(self, connector: "ChatConnector") -> dict:
        """Кнопка «Проверить соединение»: пинг списка номеров провайдера."""
        try:
            numbers = await self.fetch_numbers(connector)
            return {
                "ok": True,
                "message": f"Соединение установлено. Номеров: {len(numbers)}",
            }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"Ошибка соединения: {e}"}

    async def sync_numbers(
        self, connector: "ChatConnector", env: "Environment"
    ) -> dict:
        """Кнопка «Синхронизировать номера»: линии провайдера → реестр номеров."""
        records = await self.fetch_numbers(connector)
        return await env.models.phone_number.sync_from_provider(
            env, connector, records
        )

    async def import_history(
        self,
        connector: "ChatConnector",
        start_date: datetime,
        end_date: datetime,
        env: "Environment",
        mode: str = "silent",
    ) -> dict:
        """
        Импорт истории звонков за период (кнопка «Прочитать историю» и cron).
        Повторный импорт безопасен — звонок пишется upsert-ом по uniqueid.

        mode задаёт только лидогенерацию: normal / no_notify — с лидом,
        silent (по умолчанию) — без. Карточку импорт не показывает и не гасит.
        """
        generate_lead = LEAD_ON_IMPORT.get(mode, False)
        calls = await self.fetch_call_history(connector, start_date, end_date)
        imported = 0
        failed = 0
        for call in calls:
            try:
                await self._run_call_pipeline(
                    connector,
                    call,
                    env,
                    notify_card=False,
                    generate_lead=generate_lead,
                )
                imported += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                logger.error(
                    "[%s] import history failed: %s",
                    self.strategy_type,
                    e,
                    exc_info=True,
                )
        message = (
            f"Импортировано звонков: {imported} (из {len(calls)} записей "
            f"за период, режим «{mode}»)"
        )
        if failed:
            message += f", с ошибками: {failed}"
        return {
            "ok": True,
            "imported": imported,
            "failed": failed,
            "total": len(calls),
            "message": message,
        }
