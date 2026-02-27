from typing import TYPE_CHECKING
import pytz

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.system.schemas.base_schema import Id

if TYPE_CHECKING:
    from backend.base.crm.company.models.company import Company
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.contact import Contact

from backend.base.system.dotorm.dotorm.fields import (
    PolymorphicMany2one,
    Char,
    Integer,
    Boolean,
    Many2one,
    One2many,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

timezones = [
    (tz, tz)
    for tz in sorted(
        pytz.all_timezones,
        key=lambda tz: tz if not tz.startswith("Etc/") else "_",
    )
]


class Partner(DotModel):
    __table__ = "partners"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Partner Name")
    active: bool = Boolean(default=True)

    image: Attachment | None = PolymorphicMany2one(relation_table=Attachment)
    parent_id: "Partner | None" = Many2one(
        lambda: env.models.partner,
        string="Parent partner",
        index=True,
        ondelete="restrict",
    )
    child_ids: list["Partner"] = One2many(
        lambda: env.models.partner, "parent_id", string="Child partners"
    )
    user_id: "User | None" = Many2one(
        lambda: env.models.user,
        string="Salesperson",
        # index=True,
        ondelete="restrict",
    )
    company_id: "Company | None" = Many2one(
        lambda: env.models.company, string="Company"
    )

    tz: str = Selection(
        options=timezones,
        # default=lambda self: self._context.get("tz"),
        default="Europe/Moscow",
        string="Timezone",
    )
    lang: str = Selection(
        options=[
            ("russian", "Russian"),
            ("english", "English"),
        ],
        default="russian",
        string="Language",
    )
    vat: str | None = Char(
        string="Tax ID",
        index=True,
        help="Tax Identification Number",
    )

    # bank_ids: PartnerBank = One2many(
    #     PartnerBank, "partner_id", string="Banks"
    # )
    notes: str | None = Text(string="Notes")
    website: str | None = Char(string="Website URL")

    # Контакты (телефоны, email, telegram и т.д.)
    # Внешние аккаунты доступны через contact_ids.external_account_ids
    contact_ids: list["Contact"] = One2many(
        store=False,
        relation_table=lambda: env.models.contact,
        relation_table_field="partner_id",
        description="Контакты",
    )
