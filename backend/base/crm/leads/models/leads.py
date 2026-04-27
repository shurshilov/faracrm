from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.company.models.company import Company
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from .lead_stage import LeadStage

from ...partners.models.contact import Contact
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    One2many,
    Selection,
    Text,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.core.enviroment import env
from backend.base.crm.security.polymorphic_parent import (
    PolymorphicParentMixin,
)


class Lead(PolymorphicParentMixin):
    __table__ = "leads"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Lead Name")
    active: bool = Boolean(default=True)
    stage_id: "LeadStage" = Many2one(
        lambda: env.models.lead_stage,
        string="Stage",
        index=True,
        ondelete="restrict",
    )
    user_id: "User | None" = Many2one(
        lambda: env.models.user,
        string="Salesperson",
        # index=True,
        ondelete="restrict",
    )
    parent_id: "Partner | None" = Many2one(
        lambda: env.models.partner,
        string="Parent partner",
        index=True,
        ondelete="restrict",
    )
    company_id: "Company | None" = Many2one(
        lambda: env.models.company, string="Company"
    )
    notes: str | None = Text(string="Notes")
    type: str = Selection(
        options=[
            ("lead", "Lead"),
            ("opportunity", "Opportunity"),
        ],
        default="lead",
        string="Type",
    )
    # website: str = Char(string="Website URL")
    # email: str = Char(string="Email")
    # phone: str = Char(string="phone")
    # mobile: str = Char(string="mobile")

    # Контакты (телефоны, email, telegram и т.д.)
    # Внешние аккаунты доступны через contact_ids.external_account_ids
    contact_ids: list["Contact"] = One2many(
        store=False,
        relation_table=lambda: env.models.contact,
        relation_table_field="partner_id",
        description="Контакты",
    )
