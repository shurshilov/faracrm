# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - connector mixin

import secrets
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    Selection,
)

if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorAsteriskMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой Asterisk / FreePBX.

    Добавляет тип 'phone_asterisk' и дефолтные значения.

    Источник данных выбирается полем ``agent_mode`` (класс-стратегия транспорта,
    см. strategies/sources/):

    - ``remote`` (по умолчанию) — внешний Asterisk-agent (FastAPI рядом с Asterisk):
        * ARI-события агент шлёт на универсальный webhook FARA;
        * историю (CDR) и записи FARA тянет из REST API агента по HTTP Basic-auth.
      Поля: connector_url, access_token (login), refresh_token (password),
      webhook_url, webhook_hash.

    - ``local`` — встроенный режим (без сетевого посредника), на базе импортируемого
      пакета ``asterisk_agent``:
        * CDR читается ПРЯМО из БД Asterisk (asterisk_agent.get_db_connector);
        * записи — через ARI (asterisk_agent.Ari);
        * ARI-события слушаются in-process (asterisk_agent.WebsocketEvents).
      Настройки — отдельными типизированными колонками ``asterisk_*`` (редактируются
      как обычные поля формы; значения хранятся в БД, берутся из интерфейса).
    """

    type: str = Selection(
        selection_add=[("phone_asterisk", "Asterisk / FreePBX")]
    )

    agent_mode: str = Selection(
        options=[
            ("remote", "Удалённый агент (REST + webhook)"),
            ("local", "Встроенный (прямой доступ к БД и ARI)"),
        ],
        default="remote",
    )

    # local БД, CDR
    asterisk_db_dialect: str = Selection(
        options=[
            ("mysql", "MySQL"),
            ("postgresql", "PostgreSQL"),
            ("sqlite", "SQLite"),
        ],
        default="mysql",
    )
    asterisk_db_host: str = Char(max_length=500)
    asterisk_db_port: int = Integer(default=3306)
    asterisk_db_database: str = Char(max_length=255)
    asterisk_db_user: str = Char(max_length=255)
    asterisk_db_password: str = Char(max_length=255)
    asterisk_db_table_cdr: str = Char(max_length=128, default="cdr")

    # local ARI, события по WS и записи
    asterisk_ari_url: str = Char(max_length=500)
    asterisk_ari_wss: str = Char(max_length=500)
    asterisk_ari_login: str = Char(max_length=255)
    asterisk_ari_password: str = Char(max_length=255)

    # local: каталог с записями разговоров на сервере Asterisk (MixMonitor-файлы
    # из CDR.recordingfile). ARI /recordings/stored отдаёт ТОЛЬКО ARI-записи, а не
    # dialplan-файлы, поэтому запись читаем с диска (как agent /api/call/recording).
    # Требует, чтобы ФАРА имела доступ к этому каталогу (co-location / монтирование).
    asterisk_path_recordings: str = Char(
        max_length=500, default="/var/spool/asterisk/monitor"
    )

    # Автозапуск in-process ARI-слушателя (local). Включается свичом в форме,
    # ТОЛЬКО если проверка ARI прошла успешно; app.py на старте поднимает
    # слушатель лишь для коннекторов с этим флагом = True.
    asterisk_ari_autostart: bool = Boolean(default=False)

    # Внутренние звонки (сотрудник↔сотрудник) пишутся в direct-чат ВСЕГДА, но по
    # умолчанию БЕЗ живого попапа и без лида. Галочка → слать live-бабл участникам.
    internal_calls_notify: bool = Boolean(default=False)

    @onchange("type")
    async def onchange_type_phone_asterisk(self) -> dict:
        """Установить дефолтные значения при выборе типа phone_asterisk."""
        if self.type == "phone_asterisk":
            return {
                "webhook_hash": secrets.token_hex(32),
                "category": "phone",
            }
        return {}
