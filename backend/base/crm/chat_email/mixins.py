# Copyright 2025 FARA CRM
# Chat Email module - connector mixin

import secrets
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import (
    Selection,
    Char,
    Integer,
)

# поддержка IDE, видны все аттрибуты базового класса
if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorEmailMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой Email (SMTP/IMAP).

    Добавляет:
    - Тип 'email' в Selection поле type
    - Поля для SMTP конфигурации (отправка)
    - Поля для IMAP конфигурации (получение)
    - Метод для генерации defaults при создании

    В IDE: наследует ChatConnector - видны все поля
    В runtime: @extend применяет расширение к ChatConnector
    """

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("email", "Email")])

    # ========================================================================
    # SMTP Configuration (Outgoing)
    # ========================================================================
    smtp_host: str | None = Char(
        max_length=255,
        description="SMTP сервер (например, smtp.gmail.com)",
    )
    smtp_port: int = Integer(
        default=587,
        description="SMTP порт (587 для STARTTLS, 465 для SSL)",
    )
    smtp_encryption: str = Selection(
        options=[
            ("starttls", "STARTTLS"),
            ("ssl", "SSL/TLS"),
            ("none", "None"),
        ],
        default="starttls",
        description="Тип шифрования SMTP",
    )

    # ========================================================================
    # IMAP Configuration (Incoming)
    # ========================================================================
    imap_host: str | None = Char(
        max_length=255,
        description="IMAP сервер (например, imap.gmail.com)",
    )
    imap_port: int = Integer(
        default=993,
        description="IMAP порт (993 для SSL)",
    )
    imap_ssl: str = Selection(
        options=[
            ("ssl", "SSL/TLS"),
            ("none", "None"),
        ],
        default="ssl",
        description="Использовать SSL для IMAP",
    )
    imap_last_uid: int = Integer(
        default=1,
        description="Последний обработанный UID (для IMAP polling)",
    )

    # ========================================================================
    # Authentication
    # ========================================================================
    # Минимальный набор (90% случаев):
    # email_username = email_from в большинстве случаев
    email_username: str = Char(
        max_length=255,
        description="Логин для авторизации (email)",
    )
    email_password: str | None = Char(
        max_length=255,
        description="Пароль для авторизации",
    )

    # ========================================================================
    # Email Settings
    # ========================================================================
    # Расширенный (корпоративный):
    # Результат в письме From: "Company Support" <support@company.com>
    # Где email_from_name <email_from>

    # если отличается от username
    email_from: str | None = Char(
        max_length=255,
        description="Email адрес отправителя",
    )
    email_from_name: str | None = Char(
        max_length=255,
        description="Имя отправителя",
    )
    # если нужна маршрутизация
    email_reply_to: str | None = Char(
        max_length=255,
        description="Reply-To адрес (если отличается от email_from)",
    )
    # если нужен трекинг bounce'ов
    email_bounce: str | None = Char(
        max_length=255,
        description="Bounce адрес для Return-Path",
    )
    email_default_subject: str | None = Char(
        max_length=255,
        default="Message from FARA CRM",
        description="Тема по умолчанию",
    )

    @onchange("type")
    async def onchange_type_email(self) -> dict:
        """
        Устанавливает значения по умолчанию при выборе типа email.

        Returns:
            Словарь с дефолтными значениями для email коннектора
        """
        if self.type == "email":
            webhook_hash = secrets.token_hex(32)

            return {
                "category": "email",
                "webhook_hash": webhook_hash,
                "smtp_port": 587,
                "smtp_encryption": "starttls",
                "imap_port": 993,
                "imap_ssl": "ssl",
                "imap_last_uid": 1,
                "email_default_subject": "Message from FARA CRM",
            }
        return {}
