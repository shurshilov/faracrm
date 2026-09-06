# Copyright 2025 FARA CRM
# Leads module — Sale model extension: link to the source lead

"""
Связь «Лид → Продажа».

`Sale.lead_id` — исходный лид, из которого создана продажа (ТЗ: системное
поле «Исходный лид»). Объявлено здесь, а не в sales, чтобы модуль продаж не
зависел от лидов — так же contract добавляет Sale.contract_id (sale_ext.py).
Колонка, FK и индекс создаются auto-DDL на старте.

Ключ на стороне продажи: один лид (клиент) → много продаж (повторные заказы),
история продаж копится на карточке лида.

Регистрация: пакет leads без __init__.py, автодискавер расширений в такие
пакеты не заходит — модуль импортируется явно из leads/app.py.
"""

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import Many2one
from backend.base.crm.sales.models.sale import Sale

if TYPE_CHECKING:
    _Base = Sale
    from .leads import Lead
else:
    _Base = object


@extend(Sale)
class SaleLeadMixin(_Base):
    """Расширение Sale для модуля leads: ссылка на исходный лид."""

    lead_id: "Lead | None" = Many2one(
        lambda: env.models.lead,
        string="Source Lead",
        index=True,
        ondelete="set null",
        description="Исходный лид, из которого создана продажа",
    )
