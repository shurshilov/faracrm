# Copyright 2025 FARA CRM
# Chat module - contact routes

from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session


router_private = APIRouter(
    tags=["Chat Contacts"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


# ==================== Schemas ====================


class ContactTypeConfigResponse(BaseModel):
    """Конфиг типа контакта."""

    id: int
    name: str
    label: str
    icon: str | None
    color: str | None
    placeholder: str | None
    pattern: str | None
    connector_types: list[str]
    sequence: int


class AvailableConnectorResponse(BaseModel):
    """Доступный коннектор."""

    id: int
    name: str
    type: str

    class Config:
        from_attributes = True


class DetectContactTypeRequest(BaseModel):
    """Запрос на определение типа контакта."""

    value: str


class DetectContactTypeResponse(BaseModel):
    """Результат определения типа контакта."""

    contact_type: str | None
    label: str | None


# ==================== Routes ====================


@router_private.get(
    "/contacts/types", response_model=list[ContactTypeConfigResponse]
)
async def get_contact_types(req: Request):
    """
    Получить все типы контактов с их конфигами.

    connector_types берётся из One2many connector_ids (chat_connector.contact_type_id).
    """
    env: "Environment" = req.app.state.env

    all_types = await env.models.contact_type.search(
        filter=[("active", "=", True)],
        fields=[
            "id",
            "name",
            "label",
            "icon",
            "color",
            "placeholder",
            "pattern",
            "sequence",
            "connector_ids",
        ],
        sort="sequence",
    )

    result = []
    for ct in all_types:
        # connector_ids — One2many, содержит объекты ChatConnector
        connector_type_names = []
        if ct.connector_ids:
            for conn in ct.connector_ids:
                if hasattr(conn, "type") and conn.active:
                    connector_type_names.append(conn.type)

        result.append(
            ContactTypeConfigResponse(
                id=ct.id,
                name=ct.name,
                label=ct.label,
                icon=ct.icon,
                color=ct.color,
                placeholder=ct.placeholder,
                pattern=ct.pattern,
                connector_types=connector_type_names,
                sequence=ct.sequence,
            )
        )

    return result


@router_private.post(
    "/contacts/detect-type", response_model=DetectContactTypeResponse
)
async def detect_type(req: Request, body: DetectContactTypeRequest):
    """
    Автоопределение типа контакта по значению.

    Примеры:
    - "+79991234567" → phone
    - "ivan@mail.ru" → email
    - "@username" → telegram
    """
    env: "Environment" = req.app.state.env

    contact_type_name = await env.models.contact_type.detect_contact_type(
        body.value
    )

    if contact_type_name:
        ct = await env.models.contact_type.get_by_name(contact_type_name)
        return DetectContactTypeResponse(
            contact_type=contact_type_name,
            label=ct.label if ct else None,
        )

    return DetectContactTypeResponse(
        contact_type=None,
        label=None,
    )
