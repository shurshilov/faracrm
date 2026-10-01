# Copyright 2025 FARA CRM
# Chat module - schemas initialization

from .chat import (
    ChatCreate,
    ChatUpdate,
    AddMemberInput,
    UpdateMemberPermissions,
    ChatPin,
    MessageCreate,
    MessageEdit,
    MessagePin,
    MessageReaction,
    MessageForward,
)

__all__ = [
    "ChatCreate",
    "ChatUpdate",
    "AddMemberInput",
    "UpdateMemberPermissions",
    "ChatPin",
    "MessageCreate",
    "MessageEdit",
    "MessagePin",
    "MessageReaction",
    "MessageForward",
]
