# Copyright 2025 FARA CRM
# Chat module - schemas initialization

from .chat import (
    ChatCreate,
    ChatMember,
    ChatLastMessage,
    ChatResponse,
    ChatListResponse,
    MessageCreate,
    MessageAuthor,
    MessageResponse,
    MessageListResponse,
    ConnectorCreate,
    ConnectorResponse,
    ConnectorListResponse,
    WebSocketMessage,
    WebSocketNewMessage,
    WebSocketTyping,
    WebSocketPresence,
)

__all__ = [
    "ChatCreate",
    "ChatMember",
    "ChatLastMessage",
    "ChatResponse",
    "ChatListResponse",
    "MessageCreate",
    "MessageAuthor",
    "MessageResponse",
    "MessageListResponse",
    "ConnectorCreate",
    "ConnectorResponse",
    "ConnectorListResponse",
    "WebSocketMessage",
    "WebSocketNewMessage",
    "WebSocketTyping",
    "WebSocketPresence",
]
