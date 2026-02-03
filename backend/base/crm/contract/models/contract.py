# Copyright 2025 FARA CRM
# Contract module — Contract model

from datetime import date
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Date,
    Integer,
    Many2one,
    One2many,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.company.models.company import Company


class Contract(DotModel):
    """
    Договор с контрагентом.

    Типы: customer (с клиентом), supplier (с поставщиком), transport (на перевозку).
    """

    __table__ = "contract"

    id: int = Integer(primary_key=True)
    name: str | None = Char(string="Contract Number")
    active: bool = Boolean(default=True)

    partner_id: "Partner" = Many2one(
        lambda: env.models.partner,
        string="Counterparty",
        required=True,
        index=True,
    )
    company_id: "Company | None" = Many2one(
        lambda: env.models.company,
        string="Company",
    )

    type: str = Selection(
        options=[
            ("customer", "С клиентом"),
            ("supplier", "С поставщиком"),
            ("transport", "На перевозку"),
        ],
        default="customer",
        string="Contract Type",
    )

    date_start: date | None = Date(
        string="Start Date",
        default=date.today,
    )
    date_end: date | None = Date(
        string="End Date",
    )

    signed: bool = Boolean(
        default=False,
        string="Signed",
        help="Contract is signed by both parties",
    )
    stamp: bool = Boolean(
        default=False,
        string="Print Stamp",
        help="Include company stamp in printed documents",
    )

    notes: str | None = Text(string="Notes")

    # Связь с заказами
    sale_ids: list = One2many(
        lambda: env.models.sale,
        "contract_id",
        string="Sales Orders",
        store=False,
    )

    # @classmethod
    # def _default_date_end(cls) -> date:
    #     """По умолчанию договор на 11 месяцев."""
    #     return date.today() + relativedelta(months=11)
