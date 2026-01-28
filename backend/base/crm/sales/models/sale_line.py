from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sale import Sale
    from .tax import Tax
    from backend.base.crm.products.models.uom import Uom
    from backend.base.crm.products.models.product import Product

from backend.base.system.dotorm.dotorm.fields import (
    Float,
    Integer,
    Many2one,
    Text,
)
from backend.base.system.schemas.base_schema import Id, PositiveInt0
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


class SaleLine(DotModel):
    __table__ = "sale_line"

    id: Id = Integer(primary_key=True)
    sale_id: "Sale" = Many2one(lambda: env.models.sale, string="Sale order id")
    sequence: PositiveInt0 = Integer(string="Sequence", default=10)
    notes: str = Text(string="Notes")

    product_id: "Product" = Many2one(
        lambda: env.models.product, string="Product id"
    )

    product_uom_qty: float = Float(
        string="Quantity",
        # compute="_compute_product_uom_qty",
        default=1.0,
    )
    product_uom_id: "Uom" = Many2one(
        lambda: env.models.uom,
        # compute="_compute_product_uom",
        string="Unit of Measure",
    )
    tax_id: "Tax" = Many2one(
        lambda: env.models.tax,
        # compute="_compute_tax_id",
        string="Taxes",
    )
    price_unit: float = Float(
        string="Unit Price",
        # compute="_compute_price_unit",
    )
    discount: float = Float(
        string="Discount (%)",
        # compute="_compute_discount",
    )
    price_subtotal: float = Float(
        string="Subtotal",
        # compute="_compute_amount",
    )
    price_tax: float = Float(
        string="Total Tax",
        # compute="_compute_amount",
    )
    price_total: float = Float(
        string="Total",
        # compute="_compute_amount"
    )
