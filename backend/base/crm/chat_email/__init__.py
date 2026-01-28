# Copyright 2025 FARA CRM
# Chat Email module - SMTP/IMAP integration

from .app import ChatEmailApp
from .mixins import ChatConnectorEmailMixin

__all__ = ["ChatEmailApp", "ChatConnectorEmailMixin"]
