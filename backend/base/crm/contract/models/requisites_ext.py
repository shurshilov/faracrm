# Copyright 2025 FARA CRM
# Contract module — реквизиты РФ, общие для партнёра и компании

from backend.base.crm.company.models.company import Company
from backend.base.crm.partners.models.partners import Partner
from backend.base.system.dotorm.dotorm.fields import Char, Selection, Text
from backend.base.system.core.extensions import extend


@extend(Company)
@extend(Partner)
class RequisitesMixin:
    """
    Реквизиты, одинаковые у контрагента (Partner) и у своей организации
    (Company): тип лица, ИНН, КПП/ОГРН/ОКПО, юридический адрес, банк. Один
    класс навешан на обе модели — @extend можно стекать, каждый
    регистрирует те же поля для своей модели (Field-инстансы между
    моделями шарятся, как у AuditMixin через наследование; у поля из
    своего только name).

    Наследоваться от этого класса в других расширениях нельзя: @extend
    читает только собственный __dict__ класса, унаследованные поля не
    увидит — добавлять модель сюда ещё одним декоратором.

    Своё у Company — подписанты и печать (company_ext.py). Кнопка
    «Заполнить» по ИНН/БИК в форме — routers/requisites.py.
    """

    legal_type: str = Selection(
        options=[
            ("person", "Физическое лицо"),
            ("company", "Юридическое лицо"),
            ("entrepreneur", "Индивидуальный предприниматель"),
        ],
        default="person",
        string="Тип лица",
    )

    # ИНН — 10 цифр (юрлицо) или 12 цифр (ИП)
    vat: str | None = Char(
        string="ИНН (Tax ID)",
        max_length=12,
        index=True,
        help="Идентификационный номер налогоплательщика (Tax Identification Number)",
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
