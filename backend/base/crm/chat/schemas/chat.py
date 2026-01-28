# Copyright 2025 FARA CRM
# Chat module - Pydantic schemas for API validation

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# ====================== CHAT SCHEMAS ======================


class ChatCreate(BaseModel):
    """Schema for creating a new chat."""

    name: Optional[str] = Field(None, max_length=255, description="Chat name")
    chat_type: Literal["direct", "group", "channel"] = Field(
        "direct", description="Chat type: direct, group, channel"
    )
    user_ids: List[int] = Field(
        default_factory=list, description="User IDs for internal chat"
    )
    partner_ids: List[int] = Field(
        default_factory=list, description="Partner IDs for external chat"
    )


class ChatUpdate(BaseModel):
    """Schema for updating chat settings."""

    name: Optional[str] = Field(
        None, max_length=255, description="New chat name"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Chat description"
    )
    # Default permissions for new members
    default_can_read: Optional[bool] = Field(
        None, description="Default read permission for new members"
    )
    default_can_write: Optional[bool] = Field(
        None, description="Default write permission for new members"
    )
    default_can_invite: Optional[bool] = Field(
        None, description="Default invite permission for new members"
    )
    default_can_pin: Optional[bool] = Field(
        None, description="Default pin permission for new members"
    )
    default_can_delete_others: Optional[bool] = Field(
        None, description="Default delete others permission for new members"
    )


class AddMemberInput(BaseModel):
    """Schema for adding a member to chat."""

    user_id: int = Field(..., description="User ID to add")


class MemberPermissions(BaseModel):
    """Schema for member permissions."""

    can_read: bool = True
    can_write: bool = True
    can_invite: bool = False
    can_pin: bool = False
    can_delete_others: bool = False
    is_admin: bool = False


class ChatMember(BaseModel):
    """Schema for chat member."""

    id: int
    name: str
    email: Optional[str] = None
    member_type: Optional[str] = None
    permissions: Optional[MemberPermissions] = None


class ChatLastMessage(BaseModel):
    """Schema for last message preview."""

    id: int
    body: Optional[str] = None
    author_id: int
    create_date: Optional[datetime] = None


class ChatResponse(BaseModel):
    """Schema for chat response."""

    id: int
    name: str
    chat_type: str
    description: Optional[str] = None
    is_internal: bool = True
    is_public: bool = False
    create_date: Optional[datetime] = None
    last_message_date: Optional[datetime] = None
    members: List[ChatMember] = Field(default_factory=list)
    last_message: Optional[ChatLastMessage] = None
    unread_count: int = 0
    # Default permissions
    default_can_read: bool = True
    default_can_write: bool = True
    default_can_invite: bool = False
    default_can_pin: bool = False
    default_can_delete_others: bool = False


class ChatListResponse(BaseModel):
    """Schema for list of chats."""

    data: List[ChatResponse]
    total: int


# ====================== MESSAGE SCHEMAS ======================


class AttachmentInput(BaseModel):
    """Schema for uploading attachment with message."""

    name: str = Field(..., description="File name")
    mimetype: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")
    content: str = Field(..., description="Base64 encoded content")
    is_voice: bool = Field(False, description="Is voice message recording")


class MessageCreate(BaseModel):
    """Schema for creating a new message."""

    body: str = Field("", description="Message text")
    connector_id: Optional[int] = Field(
        None, description="Connector ID for external sending"
    )
    parent_id: Optional[int] = Field(
        None, description="Parent message ID for replies"
    )
    attachments: List[AttachmentInput] = Field(
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


class MessageAuthor(BaseModel):
    """Schema for message author."""

    id: int
    name: Optional[str] = None


class MessageResponse(BaseModel):
    """Schema for message response."""

    id: int
    body: Optional[str] = None
    message_type: str = "comment"
    create_date: Optional[datetime] = None
    author: Optional[MessageAuthor] = None
    starred: bool = False
    connector_type: Optional[str] = None


class MessageListResponse(BaseModel):
    """Schema for list of messages."""

    data: List[MessageResponse]


# ====================== CONNECTOR SCHEMAS ======================


class ConnectorCreate(BaseModel):
    """Schema for creating a connector."""

    name: str = Field(..., max_length=255)
    type: str = Field("internal", description="Connector type")
    category: str = Field("messenger", description="Connector category")
    connector_url: Optional[str] = None
    webhook_url: Optional[str] = None
    access_token: Optional[str] = None
    client_app_id: Optional[str] = None


class ConnectorResponse(BaseModel):
    """Schema for connector response."""

    id: int
    name: str
    type: str
    category: str
    active: bool = True
    webhook_state: str = "none"
    connector_url: Optional[str] = None


class ConnectorListResponse(BaseModel):
    """Schema for list of connectors."""

    data: List[ConnectorResponse]
    total: int


# ====================== WEBSOCKET SCHEMAS ======================


class WebSocketMessage(BaseModel):
    """Schema for WebSocket message."""

    type: str
    chat_id: Optional[int] = None
    message_id: Optional[int] = None
    user_id: Optional[int] = None
    data: Optional[dict] = None


class WebSocketNewMessage(BaseModel):
    """Schema for new message WebSocket event."""

    type: str = "new_message"
    chat_id: int
    message: MessageResponse
    external: bool = False


class WebSocketTyping(BaseModel):
    """Schema for typing indicator WebSocket event."""

    type: str = "typing"
    chat_id: int
    user_id: int


class WebSocketPresence(BaseModel):
    """Schema for presence WebSocket event."""

    type: str = "presence"
    user_id: int
    status: str  # online/offline
    timestamp: datetime
