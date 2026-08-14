# Copyright 2025 FARA CRM
# Chat Phone Asterisk - data source abstraction (transport strategy)

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector


class AsteriskSourceBase:
    """
    Источник данных Asterisk — Strategy на уровне транспорта.

    Инкапсулирует «откуда брать данные» о звонках, оставляя обработку звонка
    (IncomingCallPipeline) неизменной. Реализации:
      * RemoteAgentSource — REST внешнего Asterisk-agent (HTTP Basic-auth);
      * LocalAgentSource  — прямой доступ к БД Asterisk (CDR) и ARI (записи/номера),
        на базе импортируемого пакета ``asterisk_agent``.

    Все методы возвращают данные в формате CDR-записей агента (list[dict] с ключами
    calldate/src/dst/duration/billsec/disposition/uniqueid/linkedid/recordingfile/…),
    чтобы AsteriskPhoneAdapter работал одинаково для обоих источников.
    """

    def __init__(self, connector: "ChatConnector") -> None:
        self.connector = connector

    async def fetch_calls_by_id(self, uniqueid: str) -> list[dict]:
        """CDR по uniqueid/linkedid (до-запрос на завершении звонка)."""
        raise NotImplementedError

    async def fetch_call_history(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """CDR за окно [start_date, end_date] (datetime-объекты; формат под БД
        или агента выбирает реализация). cron-бэкофилл / ручной импорт."""
        raise NotImplementedError

    async def download_recording(self, filename: str) -> bytes | None:
        """Бинарь записи разговора по имени файла."""
        raise NotImplementedError

    async def list_numbers(self) -> Any:
        """Список номеров/endpoints (используется как пинг соединения)."""
        raise NotImplementedError

    async def list_ring_groups(self) -> Any:
        """Список ring groups (FreePBX). По умолчанию пусто (не FreePBX)."""
        return []

    async def list_queues(self) -> Any:
        """Список очередей queues_config (FreePBX). По умолчанию пусто."""
        return []
