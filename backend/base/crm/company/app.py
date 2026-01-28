from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class CompanyApp(App):
    """
    App auth
    """

    info = {
        "name": "Company",
        "summary": "Module allow work with company",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "company": ACL.FULL,
    }
