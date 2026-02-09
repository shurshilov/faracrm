# Copyright 2025 FARA CRM
# Chat module - routers initialization

from .chats import router_private as chats_router_private
from .messages import router_private as messages_router_private
from .connectors import router_private as connectors_router_private
from .ws import router_public as ws_router_public
from .webhook import router_public as webhook_router_public

__all__ = [
    "chats_router_private",
    "messages_router_private",
    "connectors_router_private",
    "ws_router_public",
    "webhook_router_public",
]
