# Copyright 2025 FARA CRM
# Payment module - платёж через внешнего провайдера

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal as PyDecimal
from typing import TYPE_CHECKING, Self

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Datetime,
    Decimal,
    Integer,
    Many2one,
    Selection,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.users.audit_mixin import AuditMixin
from backend.base.crm.payment.strategies import get_provider, list_providers

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User

# Комиссия площадки, % от суммы платежа.
COMMISSION_SETTING = "payment.commission_percent"


class Payment(AuditMixin, DotModel):
    """
    Платёж через внешнего провайдера.

    Модуль не знает, ЗА ЧТО платят: оплачиваемая запись — res_model/res_id;
    когда провайдер подтверждает оплату, у неё вызывается
    on_payment_paid(payment). Комиссия площадки считается здесь и уезжает
    провайдеру вместе со счётом получателя (payee_account): сумма за вычетом
    комиссии уходит получателю, комиссия остаётся владельцу терминала.
    """

    __table__ = "payment"

    id: int = Integer(primary_key=True)
    amount: float = Decimal(16, 2, default=0, description="Сумма")
    currency: str = Char(max_length=3, default="RUB")
    description: str | None = Char(max_length=255)
    state: str = Selection(
        options=[
            ("new", "Новый"),
            ("paid", "Оплачен"),
            ("failed", "Не оплачен"),
        ],
        default="new",
    )
    provider: str = Char(max_length=64, description="Провайдер оплаты")
    external_id: str | None = Char(
        max_length=128, index=True, description="ID платежа у провайдера"
    )
    payment_url: str | None = Char(
        max_length=2048, description="Ссылка на страницу оплаты"
    )
    payer_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        index=True,
        description="Плательщик",
    )
    payee_account: str | None = Char(
        max_length=128,
        description="Счёт получателя у провайдера (напр. ShopCode T-Bank)",
    )
    commission_amount: float = Decimal(
        16, 2, default=0, description="Комиссия площадки"
    )
    # Оплачиваемая запись (таблица + id); ей сообщаем об оплате.
    res_model: str | None = Char(max_length=64)
    res_id: int | None = Integer()
    paid_at: datetime | None = Datetime()

    @classmethod
    async def create_for(
        cls,
        *,
        amount,
        description: str,
        payer_id: int,
        payee_account: str | None,
        res_model: str,
        res_id: int,
        return_url: str,
    ) -> Self:
        """Создать платёж у первого подключённого провайдера."""
        providers = list_providers()
        if not providers:
            raise FaraException(
                {
                    "content": "PAYMENT_PROVIDER_NOT_CONFIGURED",
                    "detail": "Не подключён ни один платёжный провайдер",
                    "status_code": 400,
                }
            )
        provider_type = providers[0]

        percent = await env.models.system_settings.get_value(
            COMMISSION_SETTING, 10
        )
        amount = Decimal.to_decimal(amount)
        commission = (amount * PyDecimal(str(percent)) / 100).quantize(
            PyDecimal("0.01"), rounding=ROUND_HALF_UP
        )

        payment = cls(
            amount=amount,
            description=description,
            provider=provider_type,
            payer_id=env.models.user(id=payer_id),
            payee_account=payee_account,
            commission_amount=commission,
            res_model=res_model,
            res_id=res_id,
        )
        await cls.create(payload=payment)

        external_id, payment_url = await get_provider(
            provider_type
        ).create_payment(payment, return_url)
        await payment.update(
            cls(external_id=external_id, payment_url=payment_url)
        )
        return payment

    async def mark_paid(self) -> None:
        """Оплата подтверждена провайдером: закрыть платёж и сообщить записи."""
        if self.state == "paid":
            return
        await self.update(
            Payment(state="paid", paid_at=datetime.now(timezone.utc))
        )
        if not (self.res_model and self.res_id):
            return
        model = env.models._get_model(
            env.models._get_model_name_by_table(self.res_model)
        )
        record = await model.get(self.res_id)
        await record.on_payment_paid(self)

    async def mark_failed(self) -> None:
        if self.state == "new":
            await self.update(Payment(state="failed"))
