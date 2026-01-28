# Copyright 2025 FARA CRM
# Chat module initialization

from .app import ChatApp
from .models import (
    Chat,
    ChatMessage,
    ChatConnector,
    ChatExternalAccount,
    ChatExternalChat,
    ChatExternalMessage,
)
from .strategies import (
    ChatStrategyBase,
    ChatMessageAdapter,
    InternalStrategy,
    register_strategy,
    get_strategy,
    list_strategies,
)
from .websocket import ConnectionManager, chat_manager
from .routers import (
    chats_router_private,
    messages_router_private,
    connectors_router_private,
    ws_router_public,
    webhook_router_public,
)

__all__ = [
    # App
    "ChatApp",
    # Models
    "Chat",
    "ChatMessage",
    "ChatConnector",
    "ChatExternalAccount",
    "ChatExternalChat",
    "ChatExternalMessage",
    # Strategies
    "ChatStrategyBase",
    "ChatMessageAdapter",
    "InternalStrategy",
    "register_strategy",
    "get_strategy",
    "list_strategies",
    # WebSocket
    "ConnectionManager",
    "chat_manager",
    # Routers
    "chats_router_private",
    "messages_router_private",
    "connectors_router_private",
    "ws_router_public",
    "webhook_router_public",
]
