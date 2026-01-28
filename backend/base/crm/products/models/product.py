from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.company.models.company import Company
    from backend.base.crm.products.models.uom import Uom
    from backend.base.crm.products.models.category import Category

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    Selection,
    Text,
    Float,
    PolymorphicMany2one,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


class Product(DotModel):
    __table__ = "product"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Name", required=True)
    sequence: int = Integer(string="Sequence", default=1)

    description: str | None = Text(string="Description")
    type: str = Selection(
        options=[
            ("consu", "Goods"),
            ("service", "Service"),
            ("combo", "Combo"),
        ],
        default="consu",
        string="Product Type",
    )

    uom_id: "Uom | None" = Many2one(
        lambda: env.models.uom,
        string="Unit of Measure",
        # default=_get_default_uom_id,
    )
    company_id: "Company | None" = Many2one(
        lambda: env.models.company, string="Company"
    )
    category_id: "Category | None" = Many2one(
        lambda: env.models.category, string="Category"
    )

    default_code: str | None = Char(string="Internal Reference", index=True)
    code: str | None = Char(
        string="Reference",
        #  compute="_compute_"
    )
    barcode: str | None = Char(
        string="Barcode",
    )

    # product
    extra_price: float | None = Float(
        # compute="_compute_",
        string="Extra Price",
    )
    # template
    list_price: float = Float(
        string="Sales Price",
        default=1.0,
        # compute="_compute_",
        # inverse="_set_",
    )
    standard_price: float | None = Float(
        string="Cost Price",
    )

    volume: float | None = Float(string="Volume")
    weight: float | None = Float(string="Stock Weight")
    image: Attachment | None = PolymorphicMany2one(relation_table=Attachment)
