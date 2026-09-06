# Copyright 2025 FARA CRM
# Marketplace module - расширение пользователя: счёт для выплат поставщику

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.system.dotorm.dotorm.fields import Char
from backend.base.crm.users.models.users import User

# поддержка IDE, видны все атрибуты базового класса
if TYPE_CHECKING:
    _Base = User
else:
    _Base = object


@extend(User)
class UserMarketplaceMixin(_Base):
    """Счёт, на который уходит оплата за приложения поставщика."""

    payout_account: str | None = Char(
        max_length=128,
        description="Счёт получателя выплат (ShopCode у T-Bank)",
    )
