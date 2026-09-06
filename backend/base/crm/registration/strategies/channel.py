# Copyright 2025 FARA CRM
# Registration module - базовый канал доставки кода подтверждения

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.registration.models.registration import (
        Registration,
    )


class RegistrationChannelBase:
    """
    Канал, которым уходит код подтверждения регистрации.

    Конкретные каналы (email, telegram, …) живут в отдельных модулях,
    наследуют этот класс и регистрируются через register_channel — по
    аналогии со стратегиями чата. Ключ канала (channel_type) фронт
    передаёт в POST /registration.
    """

    channel_type: str = ""

    async def send_code(self, registration: "Registration") -> None:
        """Доставить registration.code на адрес registration.login."""
        raise NotImplementedError
