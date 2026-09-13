# Copyright 2025 FARA CRM
# Chat Phone module — Lead extension: звонки лида

"""
`Lead.call_ids` — звонки с привязкой к лиду (Call.lead_id; его ставит
IncomingCallPipeline: свежий лид партнёра по номеру). Объявлено здесь, а не
в leads, чтобы CRM не зависела от телефонии — так же leads добавляет
Sale.lead_id (leads/models/sale_ext.py). Вкладка «Звонки» формы лида —
fara_leads/Form.tsx, колонки — fara_telephony/CallFields.tsx.

Регистрация: chat_phone — пакет с __init__.py, поэтому *_ext.py подхватывает
автодискавер расширений (core/extensions.py), явный импорт не нужен.
"""

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import One2many
from backend.base.crm.leads.models.leads import Lead

if TYPE_CHECKING:
    _Base = Lead
    from .call import Call
else:
    _Base = object


@extend(Lead)
class LeadCallsMixin(_Base):
    """Расширение Lead для модуля телефонии: звонки лида."""

    call_ids: list["Call"] = One2many(
        store=False,
        relation_table=lambda: env.models.call,
        relation_table_field="lead_id",
        description="Звонки лида",
    )
