# Copyright 2025 FARA CRM

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Boolean,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.users.audit_mixin import AuditMixin


class UtmSource(AuditMixin, DotModel):
    """
    Источник (UTM) привязывается к сущности для атрибуции
    маркетингового источника.
    """

    __table__ = "utm_source"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=255, required=True, description="Source name")
    active: bool = Boolean(default=True)
