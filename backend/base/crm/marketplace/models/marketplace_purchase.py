# Copyright 2025 FARA CRM
# Marketplace module - покупка приложения

from typing import TYPE_CHECKING, Self

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import (
    Decimal,
    Integer,
    Many2one,
    Selection,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.base.crm.marketplace.models.marketplace_app import (
        MarketplaceApplication,
    )
    from backend.base.crm.payment.models.payment import Payment
    from backend.base.crm.users.models.users import User

# Куда провайдер вернёт покупателя после оплаты — список его покупок.
RETURN_URL = "/marketplace_purchase"


class MarketplacePurchase(AuditMixin, DotModel):
    """
    Покупка приложения. Бесплатное — сразу оплачено; платное ждёт
    подтверждения от модуля payment (on_payment_paid).
    """

    __table__ = "marketplace_purchase"

    id: int = Integer(primary_key=True)
    app_id: "MarketplaceApplication" = Many2one(
        relation_table=lambda: env.models.marketplace_app,
        required=True,
        index=True,
        ondelete="cascade",
        description="Приложение",
    )
    user_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        required=True,
        index=True,
        description="Покупатель",
    )
    amount: float = Decimal(16, 2, default=0, description="Сумма")
    state: str = Selection(
        options=[("pending", "Ожидает оплаты"), ("paid", "Оплачен")],
        default="pending",
    )
    payment_id: "Payment | None" = Many2one(
        relation_table=lambda: env.models.payment,
        ondelete="set null",
        description="Платёж",
    )

    @classmethod
    async def buy(cls, app_id: int, user_id: int) -> Self:
        """Купить приложение: вернуть оплаченную/ожидающую покупку или создать."""
        app = await env.models.marketplace_app.get(
            app_id,
            fields=["id", "name", "price", "published", "create_user_id"],
        )
        vendor_id = app.create_user_id.id if app.create_user_id else None
        if vendor_id == user_id:
            raise FaraException(
                {
                    "content": "MARKETPLACE_OWN_APP",
                    "detail": "Это ваше приложение — скачайте его из личного кабинета",
                    "status_code": 400,
                }
            )
        if not app.published:
            raise FaraException(
                {
                    "content": "MARKETPLACE_APP_NOT_PUBLISHED",
                    "detail": "Приложение не опубликовано",
                    "status_code": 400,
                }
            )

        existing = await cls.search(
            fields=["id", "state", "payment_id"],
            fields_nested={"payment_id": ["id", "state", "payment_url"]},
            filter=[("app_id", "=", app_id), ("user_id", "=", user_id)],
            sort="id",
            order="desc",
            limit=1,
        )
        if existing:
            current = existing[0]
            payment = current.payment_id
            # Уже куплено или ссылка на оплату ещё действует — не плодим покупки.
            if current.state == "paid" or (payment and payment.state == "new"):
                return current

        price = Decimal.to_decimal(app.price)
        purchase = cls(
            app_id=app,
            user_id=env.models.user(id=user_id),
            amount=price,
            state="paid" if price == 0 else "pending",
        )
        await cls.create(payload=purchase)
        if price == 0:
            return purchase

        # Счёт для выплат — в профиле поставщика; чужой профиль покупателю
        # не виден, поэтому читаем с полным доступом.
        vendor = await env.models.user.sudo().get(
            vendor_id, fields=["id", "payout_account"]
        )
        payment = await env.models.payment.create_for(
            amount=price,
            description=app.name,
            payer_id=user_id,
            payee_account=vendor.payout_account,
            res_model=cls.__table__,
            res_id=purchase.id,
            return_url=RETURN_URL,
        )
        # У покупателя нет права update на покупки (ACL create+read) —
        # платёж привязываем с полным доступом.
        await purchase.sudo().update(cls(payment_id=payment))
        purchase.payment_id = payment
        return purchase

    async def on_payment_paid(self, payment: "Payment") -> None:
        """Колбэк модуля payment после подтверждения оплаты."""
        await self.update(MarketplacePurchase(state="paid"))
