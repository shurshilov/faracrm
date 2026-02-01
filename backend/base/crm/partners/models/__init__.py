# Copyright 2025 FARA CRM
# Partners module - models initialization

from .partners import Partner
from .contact import Contact
from .contact_type import ContactType

__all__ = [
    "Partner",
    "Contact",
    "ContactType",
]
