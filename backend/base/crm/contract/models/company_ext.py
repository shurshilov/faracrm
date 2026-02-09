# Copyright 2025 FARA CRM
# Contract module — Company extension for Russian legal entities

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Many2one,
    PolymorphicMany2one,
)
from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.crm.company.models.company import Company
from backend.base.system.core.extensions import extend
from backend.base.system.core.enviroment import env

# Поддержка IDE - видны все атрибуты базового класса
if TYPE_CHECKING:
    _Base = Company
    from backend.base.crm.users.models.users import User
else:
    _Base = object


@extend(Company)
class CompanyContractMixin(_Base):
    """
    Расширение Company для работы с договорами (РФ).
    """

    # Реквизиты (могут быть related к partner_id)
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

    # Ответственные лица
    chief_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        string="Руководитель",
        help="Генеральный директор / ИП",
    )
    accountant_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        string="Главный бухгалтер",
    )

    # Печать
    stamp: Attachment | None = PolymorphicMany2one(
        relation_table=Attachment,
        string="Печать",
        help="Изображение печати организации",
    )

    # Флаги для печатных форм
    # print_stamp: bool = Boolean(
    #     default=False,
    #     string="Печатать печать",
    #     help="Добавлять печать в документы",
    # )
    # print_facsimile: bool = Boolean(
    #     default=False,
    #     string="Печатать подписи",
    #     help="Добавлять факсимиле подписей в документы",
    # )
