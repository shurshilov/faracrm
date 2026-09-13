# Copyright 2025 FARA CRM
# Contract module — Partner extension with Russian legal entity fields

from typing import TYPE_CHECKING

from backend.base.crm.partners.models.partners import Partner
from backend.base.system.dotorm.dotorm.fields import Char, Selection, Text
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

    ИНН — базовое поле Partner.vat (в интерфейсе оно подписано «ИНН»),
    отдельного поля здесь нет. Автозаполнение по ИНН и БИК — кнопка у поля
    в форме, она зовёт /requisites/party и /requisites/bank
    (routers/requisites.py), сохранение записи не затрагивается.
    """

    partner_type: str = Selection(
        options=[
            ("person", "Физическое лицо"),
            ("company", "Юридическое лицо"),
            ("entrepreneur", "Индивидуальный предприниматель"),
        ],
        default="person",
        string="Тип лица",
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

    address: str | None = Text(string="Юридический адрес")

    # Банковские реквизиты
    bank_bic: str | None = Char(string="БИК", max_length=9)
    bank_name: str | None = Char(string="Банк")
    bank_corr_account: str | None = Char(
        string="Корреспондентский счёт", max_length=20
    )
    bank_account: str | None = Char(string="Расчётный счёт", max_length=20)
