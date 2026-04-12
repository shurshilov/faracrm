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
    Text,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


async def _default_stage_id():
    """Метод для получения стадии по умолчанию"""
    first_stage = await env.models.sale_stage.search(
        fields=["id", "name"],
        limit=1,
    )
    return first_stage[0] if first_stage else None


async def _default_name():
    """Генерирует имя заказа вида 'Заказ 0000042' на основе следующего id
    из sequence таблицы sales."""
    session = env.apps.db.get_session()
    # Postgres: nextval гарантирует уникальное значение,
    # которое будет использовано при следующем INSERT
    result = await session.execute(
        "SELECT nextval(pg_get_serial_sequence('sales', 'id')) AS next_id"
    )
    next_id = result[0]["next_id"] if result else 0
    return f"Заказ {str(next_id).zfill(7)}"


class Sale(DotModel):
    __table__ = "sales"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Order Name", default=_default_name)
    active: bool = Boolean(default=True)
    stage_id: "SaleStage" = Many2one(
        lambda: env.models.sale_stage,
        string="Stage",
        index=True,
        ondelete="restrict",
        default=_default_stage_id,
    )
    user_id: "User | None" = Many2one(
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
    company_id: "Company | None" = Many2one(
        lambda: env.models.company, string="Company"
    )
    order_line_ids: list["SaleLine"] = One2many(
        lambda: env.models.sale_line, "sale_id", string="Order Lines"
    )
    notes: str | None = Text(string="Notes")
    date_order: datetime.datetime = Datetime(
        string="Order Date",
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    origin: str | None = Char(string="Source Document")
