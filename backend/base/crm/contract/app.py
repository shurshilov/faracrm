# Copyright 2025 FARA CRM
# Contract module — application

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class ContractApp(App):
    """
    Модуль договоров.

    - Договоры с контрагентами (клиенты, поставщики)
    - Расширение Partner/Company полями РФ (тип лица, КПП, ОГРН, ОКПО,
      юр. адрес, банковские реквизиты; ИНН — базовое поле vat)
    - Автозаполнение реквизитов по ИНН и банка по БИК через провайдера
      (strategies.requisites; реализация — отдельный модуль, напр. dadata)
    - Функции подготовки данных для печатных форм
    """

    info = {
        "name": "Contract",
        "summary": "Договоры с контрагентами и юридические реквизиты",
        "author": "FARA CRM",
        "category": "Sales",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["security", "partners", "company"],
    }

    BASE_USER_ACL = {
        "contract": ACL.READ_ONLY,
    }
