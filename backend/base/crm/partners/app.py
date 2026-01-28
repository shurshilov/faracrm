from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class PartnersApp(App):
    """
    App auth
    """

    info = {
        "name": "Partners",
        "summary": "Module allow work with partners",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "partner": ACL.FULL,
        "contact": ACL.FULL,
    }
