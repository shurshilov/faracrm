"""Saved filters application."""

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class SavedFiltersApp(App):
    """
    Модуль сохранённых фильтров
    """

    info = {
        "name": "Saved Filters",
        "summary": "Module for managing saved filters",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "saved_filter": ACL.FULL,
    }
