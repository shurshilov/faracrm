from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sale import Sale
    from .tax import Tax
    from backend.base.crm.products.models.uom import Uom
    from backend.base.crm.products.models.product import Product

from backend.base.system.dotorm.dotorm.decorators import onchange, depends
from backend.base.system.dotorm.dotorm.fields import (
    Decimal,
    Float,
    Integer,
    Many2one,
    Text,
)
from backend.base.system.schemas.base_schema import Id, PositiveInt0
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin


class SaleLine(AuditMixin, DotModel):
    __table__ = "sale_line"

    id: Id = Integer(primary_key=True)
    sale_id: "Sale" = Many2one(lambda: env.models.sale, string="Sale order id")
    sequence: PositiveInt0 = Integer(string="Sequence", default=10)
    notes: str | None = Text(string="Notes")

    product_id: "Product" = Many2one(
        lambda: env.models.product, string="Product id"
    )

    product_uom_qty: float = Float(
        string="Quantity",
        default=1.0,
    )
    product_uom_id: "Uom" = Many2one(
        lambda: env.models.uom,
        string="Unit of Measure",
    )
    tax_id: "Tax | None" = Many2one(
        lambda: env.models.tax,
        string="Taxes",
    )
    # Цена за единицу — деньги → Decimal.
    price_unit: float = Decimal(
        16,
        2,
        string="Unit Price",
        default=0,
    )
    # Скидка — это процент (%), не деньги → остаётся Float.
    discount: float = Float(
        string="Discount (%)",
        default=0.0,
    )
    # Вычисляемые денежные поля. compute связывает их с _compute_amount;
    # пересчёт идёт через движок @depends (write/create_bulk/onchange).
    # Округление до 2 знаков делает само поле Decimal при записи.
    price_subtotal: float = Decimal(
        16,
        2,
        string="Subtotal",
        default=0,
        compute="_compute_amount",
    )
    price_tax: float = Decimal(
        16,
        2,
        string="Total Tax",
        default=0,
        compute="_compute_amount",
    )
    price_total: float = Decimal(
        16,
        2,
        string="Total",
        default=0,
        compute="_compute_amount",
    )
    price_undiscounted: float = Decimal(
        16,
        2,
        string="Subtotal Without Discount",
        default=0,
        compute="_compute_amount",
    )

    @depends(
        triggers=[price_unit, product_uom_qty, discount, tax_id],
        prefetch=[(tax_id, "amount")],
    )
    async def _compute_amount(self) -> None:
        """Subtotal / tax / total / undiscounted по строке."""
        qty = Decimal.to_decimal(self.product_uom_qty)
        price = Decimal.to_decimal(self.price_unit)
        disc = Decimal.to_decimal(self.discount)
        gross = price * qty

        subtotal = (
            Decimal.to_decimal(0) if disc == 100 else gross * (1 - disc / 100)
        )
        tax_pct = Decimal.to_decimal(self.tax_id and self.tax_id.amount)
        tax_amount = subtotal * tax_pct / 100

        self.price_subtotal = subtotal
        self.price_tax = tax_amount
        self.price_total = subtotal + tax_amount
        self.price_undiscounted = (
            gross if disc == 100 else subtotal * 100 / (100 - disc)
        )

    @onchange("product_id")
    async def onchange_product_id(self) -> dict:
        """Значения по умолчанию при выборе product_id."""
        if self.product_id:
            product_id = await env.models.product.search(
                filter=[("id", "=", self.product_id.id)],
                fields=[
                    "id",
                    "uom_id",
                ],
                limit=1,
            )
            if product_id and product_id[0].uom_id:
                return {"product_uom_id": product_id[0].uom_id}
        return {}
