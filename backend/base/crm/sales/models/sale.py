import datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # from backend.base.crm.company.models.company import Company
    from backend.project_setup import Company
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from .sale_line import SaleLine
    from .sale_stage import SaleStage

from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Datetime,
    Integer,
    Boolean,
    Many2one,
    One2many,
    Selection,
    Text,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


class Sale(DotModel):
    __table__ = "sale"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Order Name")
    active: bool = Boolean(default=True)
    stage_id: "SaleStage" = Many2one(
        lambda: env.models.sale_stage,
        string="Stage",
        index=True,
        ondelete="restrict",
    )
    user_id: "User" = Many2one(
        lambda: env.models.user,
        string="Salesperson",
        # index=True,
        ondelete="restrict",
    )
    partner_id: "Partner" = Many2one(
        lambda: env.models.partner,
        string="Client",
        index=True,
        ondelete="restrict",
    )
    company_id: "Company" = Many2one(
        lambda: env.models.company, string="Company"
    )
    order_line_ids: list["SaleLine"] = One2many(
        lambda: env.models.sale_line, "sale_id", string="Order Lines"
    )
    notes: str | None = Text(string="Notes")
    date_order: datetime.datetime = Datetime(
        string="Order Date", default=datetime.datetime.now
    )
    origin: str = Char(string="Source Document")
