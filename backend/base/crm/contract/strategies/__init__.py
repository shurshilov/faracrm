# Copyright 2025 FARA CRM
# Contract module — реестр провайдеров реквизитов (по ИНН и БИК)

from .requisites import (
    RequisitesProviderBase,
    get_provider,
    register_provider,
)

__all__ = ["RequisitesProviderBase", "get_provider", "register_provider"]
