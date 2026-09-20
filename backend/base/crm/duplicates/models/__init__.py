# Copyright 2025 FARA CRM
# Duplicates module - models initialization

from .duplicates_ext import (
    ContactDuplicatesMixin,
    DuplicateMode,
    PartnerDuplicatesMixin,
)

__all__ = ["ContactDuplicatesMixin", "DuplicateMode", "PartnerDuplicatesMixin"]
