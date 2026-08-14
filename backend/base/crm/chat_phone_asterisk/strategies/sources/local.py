# Copyright 2025 FARA CRM
# Chat Phone Asterisk - local source (embedded asterisk_agent: direct DB + ARI)

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Callable
from asterisk_agent import (
    DbConfig,
    get_db_connector,
    Ari,
    AriConfig,
    WebsocketEvents,
)

from .base import AsteriskSourceBase

logger = logging.getLogger(__name__)


class LocalAgentSource(AsteriskSourceBase):
    """
    Встроенный источник: прямой доступ к БД Asterisk (CDR) и ARI, на базе
    импортируемого пакета ``asterisk_agent``. Не требует внешнего Asterisk-agent
    и HTTP-хопа — «фара ходит в CDR» сама.

    Настройки берутся из ТИПИЗИРОВАННЫХ КОЛОНОК коннектора (asterisk_db_* / asterisk_ari_*),
    которые редактируются в форме коннектора и хранятся в БД (см. mixins.py).
    Пакет ``asterisk_agent`` импортируется лениво (внутри методов), чтобы модуль
    оставался импортируемым, даже если пакет ещё не установлен (remote-режим).
    """

    # ARI-события, интересные для звонков (фильтрация — внутри пакета). Разумные
    # дефолты FreePBX; при необходимости вынести в колонки — тривиально.
    DEFAULT_ARI_EVENTS_USED = [
        "ChannelStateChange",
        "ChannelDestroyed",
        "ChannelHangupRequest",
    ]
    DEFAULT_ARI_EVENTS_IGNORE = ["ChannelVarset", "ChannelDialplan"]

    def _db_connector(self):
        cfg = DbConfig(
            db_dialect=self.connector.asterisk_db_dialect,
            db_host=self.connector.asterisk_db_host,
            db_port=self.connector.asterisk_db_port,
            db_database=self.connector.asterisk_db_database,
            db_user=self.connector.asterisk_db_user,
            db_password=self.connector.asterisk_db_password,
            db_table_cdr_name=self.connector.asterisk_db_table_cdr,
        )
        return get_db_connector(cfg)

    def _ari_client(self):
        login = self.connector.asterisk_ari_login
        password = self.connector.asterisk_ari_password
        return Ari(
            ari_url=self.connector.asterisk_ari_url,
            api_key=f"{login}:{password}",
        )

    @staticmethod
    def _rows_to_dicts(rows) -> list[dict]:
        """CDR-строки list[dict] (aiomysql DictCursor / aiosqlite.Row to dict)."""
        out = []
        for row in rows or []:
            try:
                out.append(dict(row))
            except (TypeError, ValueError):
                out.append(row)
        return out

    # pull
    async def fetch_calls_by_id(self, uniqueid: str) -> list[dict]:
        db = self._db_connector()
        rows = await db.get_cdr_uniqueid_or_linkedid(uniqueid)
        return self._rows_to_dicts(rows)

    async def fetch_call_history(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        db = self._db_connector()
        # определить колонку старта (calldate vs start)
        await db.check_cdr_old()
        # CDR-литерал БД — наивный локальный «YYYY-MM-DD HH:MM:SS» (MariaDB не
        # парсит ISO-"T"/оффсет). aware → приводим к локальному наивному.
        fmt = "%Y-%m-%d %H:%M:%S"
        rows = await db.get_cdr(
            start_date.astimezone().strftime(fmt),
            end_date.astimezone().strftime(fmt),
        )
        return self._rows_to_dicts(rows)

    async def download_recording(self, filename: str) -> bytes | None:
        """
        Запись разговора читаем С ДИСКА (MixMonitor-файл из CDR.recordingfile),
        как рабочий agent-роут /api/call/recording (os.walk по каталогу записей).

        ВАЖНО: ARI /recordings/stored отдаёт ТОЛЬКО ARI-записи, а не dialplan-файлы
        (MixMonitor), поэтому им НЕ пользуемся — на нём запись всегда пустая.
        Требует доступ ФАРЫ к каталогу asterisk_path_recordings (co-location /
        монтирование). Чтение — в потоке, чтобы не блокировать event loop.
        """
        if not filename:
            return None
        path_root = self.connector.asterisk_path_recordings
        if not path_root:
            logger.warning(
                "[phone_asterisk] asterisk_path_recordings не задан — запись "
                "%s не прочитать (local-режим читает файл с диска)",
                filename,
            )
            return None
        content = await asyncio.to_thread(
            self._read_recording_from_disk, path_root, filename
        )
        if not content:
            logger.warning(
                "[phone_asterisk] запись %s не найдена в %s (проверьте путь и "
                "доступ ФАРЫ к каталогу записей Asterisk)",
                filename,
                path_root,
            )
        return content or None

    @staticmethod
    def _read_recording_from_disk(
        path_root: str, filename: str
    ) -> bytes | None:
        """
        Найти файл записи по ИМЕНИ (basename) в дереве каталога и вернуть байты.
        recordingfile из CDR может нести подпуть (FreePBX: YYYY/MM/DD/имя) —
        сравниваем по basename, os.walk обходит подкаталоги (как agent-роут).
        """
        target = os.path.basename(filename)
        for root, _dirs, files in os.walk(path_root):
            if target in files:
                try:
                    with open(os.path.join(root, target), "rb") as f:
                        return f.read()
                except OSError:
                    return None
        return None

    async def list_numbers(self):
        text = await self._ari_client().numbers()
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # ARI вернул не-JSON (обычно 401/404 — неверный ARI url/логин/пароль
            # или неправильный путь). Логируем сырой ответ, чтобы было видно причину.
            logger.warning(
                "[phone_asterisk] ARI /endpoints вернул не-JSON "
                "(проверьте asterisk_ari_url/login/password): %s",
                (text or "")[:500],
            )
            return []
        if not isinstance(data, list):
            # ARI-ошибка (напр. 401 → {"message": ...}) — это не список endpoints.
            logger.warning(
                "[phone_asterisk] ARI /endpoints вернул не-список (ошибка ARI?): %s",
                str(data)[:500],
            )
            return []
        return data

    async def list_ring_groups(self):
        # FreePBX: asterisk.ringgroups (прямой SQL через пакет)
        rows = await self._db_connector().get_ring_groups()
        return self._rows_to_dicts(rows)

    async def list_queues(self):
        # FreePBX: asterisk.queues_config (прямой SQL через пакет)
        rows = await self._db_connector().get_queues_config()
        return self._rows_to_dicts(rows)

    # ARI WebSocket, in-process
    @staticmethod
    def build_ws(connector, on_event: Callable):
        """
        Собрать asterisk_agent.WebsocketEvents для in-process приёма ARI-событий.

        on_event(event: dict) — async-колбэк на каждое ОТФИЛЬТРОВАННОЕ ARI-событие
        (фильтрация events_used / events_ignore — внутри пакета). Запускать через
        ``asyncio.create_task(ws.run_forever())`` (см. app.py).
        """

        login = connector.asterisk_ari_login
        password = connector.asterisk_ari_password
        ari_config = AriConfig(
            url=connector.asterisk_ari_url,
            wss=connector.asterisk_ari_wss,
            login=login,
            password=password,
            events_ignore=LocalAgentSource.DEFAULT_ARI_EVENTS_IGNORE,
            events_used=LocalAgentSource.DEFAULT_ARI_EVENTS_USED,
        )
        return WebsocketEvents(
            api_key_base64="",
            api_key=f"{login}:{password}",
            ari_config=ari_config,
            on_event=on_event,
        )
