# Copyright 2025 FARA CRM
# Chat Phone module — Sale extension: звонки клиента заказа

"""
`Sale.call_ids` — звонки клиента заказа. У звонка нет sale_id, ключ —
партнёр (Call.partner_id): виджет One2many на форме заказа подставляет
владельца из partner_id заказа (parentField), а не id самого заказа — как
контакты партнёра на лиде (Lead.contact_ids). Объявлено здесь, чтобы
продажи не зависели от телефонии. Вкладка «Звонки» — fara_sales/Form.tsx.

Регистрация: автодискавер *_ext.py (chat_phone — пакет с __init__.py).
"""

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import One2many
from backend.base.crm.sales.models.sale import Sale

if TYPE_CHECKING:
    _Base = Sale
    from .call import Call
else:
    _Base = object


@extend(Sale)
class SaleCallsMixin(_Base):
    """Расширение Sale для модуля телефонии: звонки клиента."""

    call_ids: list["Call"] = One2many(
        store=False,
        relation_table=lambda: env.models.call,
        relation_table_field="partner_id",
        description="Звонки клиента заказа",
    )
