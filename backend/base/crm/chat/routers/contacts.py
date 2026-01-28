# Copyright 2025 FARA CRM
# Chat module - contact routes

from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.partners.models.contact import (
    CONTACT_TYPE_CONFIG,
    CONTACT_TYPE_CONNECTORS,
    Contact,
)

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

    name: str
    label: str
    icon: str | None
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
async def get_contact_types():
    """
    Получить все типы контактов с их конфигами.

    Используется для:
    - Виджета ввода контактов (ContactsWidget)
    - Выпадающего списка типов
    """
    result = []

    for name, config in CONTACT_TYPE_CONFIG.items():
        result.append(
            ContactTypeConfigResponse(
                name=name,
                label=config.get("label", name),
                icon=config.get("icon"),
                placeholder=config.get("placeholder"),
                pattern=config.get("pattern"),
                connector_types=CONTACT_TYPE_CONNECTORS.get(name, []),
                sequence=config.get("sequence", 99),
            )
        )

    # Сортируем по sequence
    result.sort(key=lambda x: x.sequence)

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
    contact_type = Contact.detect_contact_type(body.value)

    if contact_type:
        config = CONTACT_TYPE_CONFIG.get(contact_type, {})
        return DetectContactTypeResponse(
            contact_type=contact_type,
            label=config.get("label"),
        )

    return DetectContactTypeResponse(
        contact_type=None,
        label=None,
    )
