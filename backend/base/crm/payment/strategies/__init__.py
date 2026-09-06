# Copyright 2025 FARA CRM
# Payment module - реестр платёжных провайдеров

import logging
from typing import Type

from backend.base.system.core.exceptions.environment import FaraException
from .provider import PaymentProviderBase

logger = logging.getLogger(__name__)

_providers: dict[str, PaymentProviderBase] = {}


def register_provider(provider_class: Type[PaymentProviderBase]) -> None:
    """Зарегистрировать провайдера (вызывается из __init__ его модуля)."""
    provider = provider_class()
    _providers[provider.provider_type] = provider
    logger.info("Registered payment provider: %s", provider.provider_type)


def get_provider(provider_type: str) -> PaymentProviderBase:
    if provider_type not in _providers:
        raise FaraException(
            {
                "content": "PAYMENT_PROVIDER_UNKNOWN",
                "detail": f"Платёжный провайдер не подключён: {provider_type}",
                "status_code": 400,
            }
        )
    return _providers[provider_type]


def list_providers() -> list[str]:
    return list(_providers)


__all__ = [
    "PaymentProviderBase",
    "register_provider",
    "get_provider",
    "list_providers",
]
