# Copyright 2025 FARA CRM
# Contract module — Partner extension with Russian legal entity fields

from typing import TYPE_CHECKING

from backend.base.crm.partners.models.partners import Partner
from backend.base.system.dotorm.dotorm.fields import Char
from backend.base.system.core.extensions import extend

# Поддержка IDE - видны все атрибуты базового класса
if TYPE_CHECKING:
    _Base = Partner
else:
    _Base = object


@extend(Partner)
class PartnerContractMixin(_Base):
    """
    Расширение Partner для работы с договорами (РФ).
    """

    # ИНН — 10 цифр (юрлицо) или 12 цифр (физлицо/ИП)
    inn: str | None = Char(
        string="ИНН",
        max_length=12,
        index=True,
        help="Идентификационный номер налогоплательщика",
    )

    # КПП — 9 цифр, только для юрлиц
    kpp: str | None = Char(
        string="КПП",
        max_length=9,
        help="Код причины постановки на учёт (только для организаций)",
    )

    # ОГРН — 13 цифр (юрлицо) или 15 цифр (ИП — ОГРНИП)
    ogrn: str | None = Char(
        string="ОГРН",
        max_length=15,
        help="Основной государственный регистрационный номер",
    )

    # ОКПО — 8 цифр (юрлицо) или 10 цифр (ИП)
    okpo: str | None = Char(
        string="ОКПО",
        max_length=14,
        help="Общероссийский классификатор предприятий и организаций",
    )
