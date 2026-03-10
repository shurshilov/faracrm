# Copyright 2025 FARA CRM
# Chat module - Web Push message adapter

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class WebPushMessageAdapter(ChatMessageAdapter):
    """
    Adapter for Web Push.
    Web Push is one-directional (server -> client),
    so incoming messages via webhook are not supported.
    This adapter exists for interface compatibility.
    """

    @property
    def message_id(self):
        return str(self.raw.get("id", ""))

    @property
    def chat_id(self):
        return str(self.raw.get("chat_id", ""))

    @property
    def author_id(self):
        return str(self.raw.get("author_id", ""))

    @property
    def text(self):
        return self.raw.get("body")

    @property
    def created_at(self):
        return self.raw.get("created_at", 0)

    @property
    def should_skip(self):
        return True
