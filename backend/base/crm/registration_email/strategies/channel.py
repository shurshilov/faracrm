# Copyright 2025 FARA CRM
# Registration Email module - код подтверждения письмом

import html
import json
from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.crm.chat.strategies import get_strategy
from backend.base.crm.registration.models.registration import CODE_TTL
from backend.base.crm.registration.strategies.channel import (
    RegistrationChannelBase,
)

if TYPE_CHECKING:
    from backend.base.crm.registration.models.registration import (
        Registration,
    )

# ID email-коннектора, которым уходят письма. Пусто — первый активный.
CONNECTOR_SETTING = "registration_email.connector_id"


class EmailRegistrationChannel(RegistrationChannelBase):
    """
    Код подтверждения письмом через штатный email-коннектор чата.

    Письмо уходит SMTP-учёткой коннектора — то есть от имени администратора,
    который его настроил. Тема и html едут внутри body — это «email-формат»
    стратегии (см. parse_email_body), отдельный отправитель не нужен.
    """

    channel_type = "email"

    async def send_code(self, registration: "Registration") -> None:
        if "@" not in registration.login:
            raise FaraException(
                {
                    "content": "REGISTRATION_EMAIL_INVALID",
                    "detail": "Укажите корректный email",
                    "status_code": 400,
                }
            )
        connector = await self._connector()
        minutes = int(CODE_TTL.total_seconds() // 60)
        body = json.dumps(
            {
                "subject": f"Код подтверждения регистрации: {registration.code}",
                "html": (
                    f"<p>Здравствуйте, {html.escape(registration.name)}!</p>"
                    f"<p>Ваш код подтверждения: <b>{registration.code}</b></p>"
                    f"<p>Код действует {minutes} минут.</p>"
                ),
            }
        )
        try:
            await get_strategy("email").chat_send_message(
                connector=connector,
                user_from=None,
                body=body,
                chat_id=registration.login,
            )
        except ValueError as e:
            # Стратегия заворачивает ошибки SMTP в ValueError; без этого они
            # уходят на фронт безликим 500 — причину увидит только лог.
            raise FaraException(
                {
                    "content": "REGISTRATION_EMAIL_SEND_FAILED",
                    "detail": f"Не удалось отправить письмо: {e}",
                    "status_code": 500,
                }
            ) from e

    @staticmethod
    async def _connector():
        connector_id = await env.models.system_settings.get_value(
            CONNECTOR_SETTING
        )
        if connector_id:
            filter_ = [("id", "=", int(connector_id))]
        else:
            filter_ = [("type", "=", "email"), ("active", "=", True)]
        connectors = await env.models.chat_connector.search(
            filter=filter_, sort="id", order="asc", limit=1
        )
        if not connectors:
            raise FaraException(
                {
                    "content": "REGISTRATION_EMAIL_NOT_CONFIGURED",
                    "detail": "Email-коннектор для писем подтверждения не настроен",
                    "status_code": 500,
                }
            )
        return connectors[0]
