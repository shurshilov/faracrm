# Copyright 2025 FARA CRM
# Contract module — реквизиты по ИНН и банк по БИК для кнопки «Заполнить»
#
# Ручки только ЧИТАЮТ у провайдера и отдают значения полей RequisitesMixin
# (одни имена у партнёра и компании) — форма подставляет их сама, а
# сохраняет пользователь как обычно. В БД здесь ничего не пишется.

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.contract.strategies import get_provider
from backend.base.system.core.exceptions.environment import FaraException

if TYPE_CHECKING:
    from backend.base.crm.contract.strategies import RequisitesProviderBase

router_private = APIRouter(
    tags=["Contract"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


def _provider() -> "RequisitesProviderBase":
    provider = get_provider()
    if provider is None:
        raise FaraException(
            {
                "content": "REQUISITES_PROVIDER_MISSING",
                "detail": (
                    "Автозаполнение реквизитов не подключено: установите "
                    "модуль DaData в «Приложениях»"
                ),
                "status_code": 400,
            }
        )
    return provider


def _digits(value: str, lengths: tuple[int, ...], what: str) -> str:
    value = (value or "").strip()
    if not value.isdigit() or len(value) not in lengths:
        expected = " или ".join(str(n) for n in lengths)
        raise FaraException(
            {
                "content": "REQUISITES_BAD_QUERY",
                "detail": f"{what} — это {expected} цифр",
                "status_code": 400,
            }
        )
    return value


@router_private.get("/requisites/party")
async def party_by_inn(req: Request, inn: str) -> dict:
    """Юрлицо/ИП по ИНН → поля партнёра (пусто — не найдено)."""
    return await _provider().party_by_inn(_digits(inn, (10, 12), "ИНН"))


@router_private.get("/requisites/bank")
async def bank_by_bic(req: Request, bic: str) -> dict:
    """Банк по БИК → поля партнёра (пусто — не найдено)."""
    return await _provider().bank_by_bic(_digits(bic, (9,), "БИК"))
