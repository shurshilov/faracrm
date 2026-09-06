# Copyright 2025 FARA CRM
# Registration module - реестр каналов доставки кода

import logging
from typing import Type

from backend.base.system.core.exceptions.environment import FaraException
from .channel import RegistrationChannelBase

logger = logging.getLogger(__name__)

_channels: dict[str, RegistrationChannelBase] = {}


def register_channel(channel_class: Type[RegistrationChannelBase]) -> None:
    """Зарегистрировать канал (вызывается из __init__ модуля-канала)."""
    channel = channel_class()
    _channels[channel.channel_type] = channel
    logger.info("Registered registration channel: %s", channel.channel_type)


def get_channel(channel_type: str) -> RegistrationChannelBase:
    if channel_type not in _channels:
        raise FaraException(
            {
                "content": "REGISTRATION_CHANNEL_UNKNOWN",
                "detail": f"Канал регистрации не подключён: {channel_type}",
                "status_code": 400,
            }
        )
    return _channels[channel_type]


__all__ = ["RegistrationChannelBase", "register_channel", "get_channel"]
