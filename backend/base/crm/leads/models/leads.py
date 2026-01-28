from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.company.models.company import Company
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from .lead_stage import LeadStage

from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    Selection,
    Text,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


class Lead(DotModel):
    __table__ = "lead"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Lead Name")
    active: bool = Boolean(default=True)
    stage_id: "LeadStage" = Many2one(
        lambda: env.models.lead_stage,
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
    parent_id: "Partner" = Many2one(
        lambda: env.models.partner,
        string="Parent partner",
        index=True,
        ondelete="restrict",
    )
    company_id: "Company" = Many2one(
        lambda: env.models.company, string="Company"
    )
    notes: str = Text(string="Notes")
    type: str = Selection(
        options=[
            ("lead", "Lead"),
            ("opportunity", "Opportunity"),
        ],
        default="lead",
        string="Type",
    )
    website: str = Char(string="Website URL")
    email: str = Char(string="Email")
    phone: str = Char(string="phone")
    mobile: str = Char(string="mobile")
