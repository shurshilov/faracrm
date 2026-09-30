# Copyright 2025 FARA CRM
# Contract module — Sale model extension: link to the contract

"""
Связь «Продажа → Договор».

`Sale.contract_id` — обратная сторона Contract.sale_ids. Объявлено здесь, а
не в sales, чтобы модуль продаж не зависел от договоров. Функции данных
печатных форм по продажам (счёт на оплату и т.п.) живут в модуле
sales_report_docx (models/sale_ext.py).
"""

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import Many2one
from backend.base.crm.sales.models.sale import Sale

if TYPE_CHECKING:
    _Base = Sale
    from backend.base.crm.contract.models.contract import Contract
else:
    _Base = object


@extend(Sale)
class SaleContractMixin(_Base):
    """Расширение Sale для модуля contract: ссылка на договор."""

    contract_id: "Contract | None" = Many2one(
        lambda: env.models.contract,
        string="Договор",
        index=True,
    )
