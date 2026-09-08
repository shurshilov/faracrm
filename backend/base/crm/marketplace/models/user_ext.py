# Copyright 2025 FARA CRM
# Marketplace module - расширение пользователя: счёт для выплат поставщику

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.system.dotorm.dotorm.fields import Boolean, Char
from backend.base.crm.users.models.users import User

# поддержка IDE, видны все атрибуты базового класса
if TYPE_CHECKING:
    _Base = User
else:
    _Base = object


@extend(User)
class UserMarketplaceMixin(_Base):
    """Поставщик маркетплейса: счёт для выплат и отметка «подтверждён»."""

    payout_account: str | None = Char(
        max_length=128,
        description="Счёт получателя выплат (ShopCode у T-Bank)",
    )
    # Ставит только system_admin (или суперпользователь) — в форме юзера.
    verified: bool = Boolean(
        default=False,
        role_create="system_admin",
        role_update="system_admin",
        description="Подтверждённый продавец",
    )
