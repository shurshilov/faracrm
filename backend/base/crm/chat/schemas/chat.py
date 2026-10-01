# Copyright 2025 FARA CRM
# Chat module - Pydantic schemas for API validation

from typing import Literal
from pydantic import BaseModel, Field

from backend.base.system.dotorm.dotorm.integrations.pydantic import (
    Base64DecodedBytes,
)

# ====================== CHAT SCHEMAS ======================


class ChatCreate(BaseModel):
    """Schema for creating a new chat."""

    name: str | None = Field(None, max_length=255, description="Chat name")
    chat_type: Literal["direct", "group", "channel"] = Field(
        "direct", description="Chat type: direct, group, channel"
    )
    user_ids: list[int] = Field(
        default_factory=list, description="User IDs for internal chat"
    )
    partner_ids: list[int] = Field(
        default_factory=list, description="Partner IDs for external chat"
    )


class ChatUpdate(BaseModel):
    """Schema for updating chat settings."""

    name: str | None = Field(None, max_length=255, description="New chat name")
    description: str | None = Field(
        None, max_length=1000, description="Chat description"
    )
    # Default permissions for new members
    default_can_read: bool | None = Field(
        None, description="Default read permission for new members"
    )
    default_can_write: bool | None = Field(
        None, description="Default write permission for new members"
    )
    default_can_invite: bool | None = Field(
        None, description="Default invite permission for new members"
    )
    default_can_remove: bool | None = Field(
        None, description="Default remove-members permission for new members"
    )
    default_can_pin: bool | None = Field(
        None, description="Default pin permission for new members"
    )
    default_can_delete_others: bool | None = Field(
        None, description="Default delete others permission for new members"
    )


class AddMemberInput(BaseModel):
    """Schema for adding a member to chat."""

    user_id: int = Field(..., description="User ID to add")


class UpdateMemberPermissions(BaseModel):
    """Schema for partial update of member permissions (PATCH)."""

    can_read: bool | None = None
    can_write: bool | None = None
    can_invite: bool | None = None
    can_remove: bool | None = None
    can_pin: bool | None = None
    can_delete_others: bool | None = None
    is_admin: bool | None = None


# ====================== MESSAGE SCHEMAS ======================


class AttachmentInput(BaseModel):
    """Schema for uploading attachment with message."""

    name: str = Field(..., description="File name")
    mimetype: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")
    content: Base64DecodedBytes = Field(
        ...,
        description="File content (base64-encoded on the wire, decoded to bytes)",
    )
    is_voice: bool = Field(False, description="Is voice message recording")


class MessageCreate(BaseModel):
    """Schema for creating a new message."""

    body: str = Field("", description="Message text")
    connector_id: int | None = Field(
        None, description="Connector ID for external sending"
    )
    parent_id: int | None = Field(
        None, description="Parent message ID for replies"
    )
    # Тег «ленты»: к какому лиду относится это (исходящее) сообщение. Передаёт
    # вызывающий — обычно панель ленты в форме лида. NULL = вне лида (партнёр-
    # скоуп). Проставляется в message.lead_id через post_message.
    lead_id: int | None = Field(
        None, description="Lead the message belongs to (feed tag)"
    )
    task_id: int | None = Field(
        None, description="Task the message belongs to (feed tag)"
    )
    attachments: list[AttachmentInput] = Field(
        default_factory=list, description="Attachments to upload"
    )


class MessageEdit(BaseModel):
    """Schema for editing a message."""

    body: str = Field(..., description="New message text")


class MessagePin(BaseModel):
    """Schema for pinning a message."""

    pinned: bool = Field(..., description="Pin status")


class MessageReaction(BaseModel):
    """Schema for adding a reaction to a message."""

    emoji: str = Field(..., max_length=10, description="Emoji reaction")


class MessageForward(BaseModel):
    """Schema for forwarding a message."""

    target_chat_id: int = Field(..., description="Target chat ID")


# ====================== PIN SCHEMA ======================
# Папки чатов управляются через auto-CRUD (/auto/chat_folder) — отдельных
# folder-схем/роутера нет. Здесь остаётся только действие закрепления чата.


class ChatPin(BaseModel):
    """Schema for pinning/unpinning a chat for the current user."""

    pinned: bool = Field(..., description="Pin status")
