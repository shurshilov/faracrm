from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    One2many,
    PolymorphicMany2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.attachments.models.attachments import Attachment


class Company(DotModel):
    __table__ = "company"

    id: int = Integer(primary_key=True)
    name: str = Char(string="Company Name")
    active: bool = Boolean(default=True)
    sequence: int = Integer(
        help="Used to order Companies in the company switcher", default=10
    )
    parent_id: "Company | None" = Many2one(
        lambda: env.models.company,
        string="Parent Company",
        index=True,
        ondelete="restrict",
    )
    child_ids: list["Company"] = One2many(
        lambda: env.models.company, "parent_id", string="Child companies"
    )

    logo_id: "Attachment | None" = PolymorphicMany2one(
        relation_table=Attachment,
    )
    login_logo_id: "Attachment | None" = PolymorphicMany2one(
        relation_table=Attachment,
    )
    login_background_id: "Attachment | None" = PolymorphicMany2one(
        relation_table=Attachment,
    )

    # Тексты на странице входа
    login_title: str | None = Char(
        string="Login title",
        description="Заголовок на странице входа",
    )
    login_subtitle: str | None = Char(
        string="Login subtitle",
        description="Подзаголовок (под логотипом) на странице входа",
    )
