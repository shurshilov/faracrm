# Copyright 2025 FARA CRM
# DaData module — провайдер реквизитов через API подсказок DaData
#
# Используется только «Подсказки» (suggestions API): findById/party — юрлицо
# или ИП по ИНН, findById/bank — банк по БИК. Этот API бесплатен в пределах
# дневного лимита (10 000 запросов), нужен один ключ из личного кабинета
# dadata.ru. Платная «Стандартизация» (cleaner, секретный ключ) не нужна.

import logging

import httpx

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.crm.contract.strategies import RequisitesProviderBase

logger = logging.getLogger(__name__)

SETTING_API_KEY = "dadata.api_key"
API_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/"

# Тип организации DaData → Partner.partner_type. Физлиц в ЕГРЮЛ/ЕГРИП нет,
# поэтому их ИНН просто ничего не находит.
PARTNER_TYPE = {"LEGAL": "company", "INDIVIDUAL": "entrepreneur"}


class DadataProvider(RequisitesProviderBase):
    app_code = "dadata"
    TIMEOUT = 10

    async def party_by_inn(self, inn: str) -> dict:
        # У юрлица с филиалами на один ИНН несколько записей с разными КПП;
        # нам нужна головная организация (branch_type MAIN).
        suggestions = await self._find("party", inn, count=20)
        chosen = next(
            (
                s
                for s in suggestions
                if s.get("data", {}).get("branch_type") != "BRANCH"
            ),
            suggestions[0] if suggestions else None,
        )
        if not chosen:
            return {}
        data = chosen.get("data") or {}
        name = data.get("name") or {}
        address = data.get("address") or {}
        return {
            "name": name.get("short_with_opf") or chosen.get("value"),
            "partner_type": PARTNER_TYPE.get(data.get("type"), "company"),
            "kpp": data.get("kpp") or None,
            "ogrn": data.get("ogrn") or None,
            "okpo": data.get("okpo") or None,
            "address": address.get("unrestricted_value")
            or address.get("value")
            or None,
        }

    async def bank_by_bic(self, bic: str) -> dict:
        suggestions = await self._find("bank", bic, count=1)
        if not suggestions:
            return {}
        chosen = suggestions[0]
        data = chosen.get("data") or {}
        name = data.get("name") or {}
        return {
            "bank_name": name.get("payment") or chosen.get("value"),
            "bank_corr_account": data.get("correspondent_account") or None,
        }

    async def _find(self, resource: str, query: str, **params) -> list[dict]:
        """POST findById/<resource> → список suggestions (пустой = не найдено)."""
        # Настройки закрыты обычному сотруднику, а реквизиты подтягивает
        # именно он — читаем ключ под системной сессией.
        key = await env.models.system_settings.sudo().get_value(
            SETTING_API_KEY, ""
        )
        if not key:
            raise FaraException(
                {
                    "content": "DADATA_NOT_CONFIGURED",
                    "detail": (
                        "Укажите ключ API DaData в системных настройках "
                        f"({SETTING_API_KEY})"
                    ),
                    "status_code": 400,
                }
            )
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.post(
                    API_URL + resource,
                    json={"query": query, **params},
                    headers={
                        "Authorization": f"Token {key}",
                        "Accept": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            raise FaraException(
                {
                    "content": "DADATA_UNAVAILABLE",
                    "detail": f"DaData недоступен: {exc}",
                    "status_code": 400,
                }
            )
        if response.status_code in (401, 403):
            raise FaraException(
                {
                    "content": "DADATA_AUTH_FAILED",
                    "detail": "DaData отклонил ключ API — проверьте настройку",
                    "status_code": 400,
                }
            )
        if response.status_code != 200:
            logger.warning(
                "DaData %s → %s: %s",
                resource,
                response.status_code,
                response.text[:200],
            )
            raise FaraException(
                {
                    "content": "DADATA_ERROR",
                    "detail": f"DaData ответил кодом {response.status_code}",
                    "status_code": 400,
                }
            )
        return response.json().get("suggestions") or []
