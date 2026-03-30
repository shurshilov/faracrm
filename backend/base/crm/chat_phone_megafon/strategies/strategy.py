# Copyright 2025 FARA CRM
# Chat Phone MegaFon module - MegaFon VATS strategy

import logging
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat_phone.strategies.strategy import PhoneStrategyBase
from .adapter import MegafonPhoneAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.partners.models.contact import Contact

logger = logging.getLogger(__name__)


class MegafonPhoneStrategy(PhoneStrategyBase):
    """
    Стратегия для интеграции с МегаФон ВАТС (Виртуальная АТС).

    MegaFon REST API:
    - Base URL: https://{domain}/crmapi/v1/
    - Auth: X-API-KEY header
    - Docs: https://api.megapbx.ru/

    Webhook (входящие от MegaFon → FARA):
    - Один URL для всех команд: /chat/webhook/{hash}/{connector_id}
    - Аутентификация: crm_token в теле POST (сравнивается с vpbx_api_key)
    - Команды: history, event, contact, rating

    Поддерживает:
    - Приём событий звонков (event: INCOMING/ACCEPTED/COMPLETED/CANCELLED)
    - Приём завершённых звонков с записью (history)
    - Получение истории звонков через API
    - Синхронизация операторов/номеров
    - Инициация исходящих звонков (make_call)

    Настройка полей ChatConnector:
    - connector_url: https://{domain}/crmapi/v1
    - access_token: API ключ (X-API-KEY для исходящих запросов)
    - vpbx_api_key: CRM токен (для валидации входящих webhook)
    """

    strategy_type = "phone_megafon"
    TIMEOUT = 30.0

    # ========================================================================
    # Абстрактные методы ChatStrategyBase
    # ========================================================================

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """MegaFon использует статичный API ключ, обновление не требуется."""
        return connector.access_token

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        MegaFon VATS webhook настраивается в личном кабинете.
        URL: https://your-domain/chat/webhook/{hash}/{connector_id}

        Проверяем доступность API для валидации настроек.
        """
        try:
            # Проверяем что API доступен
            users = await self._api_request(connector, "/users")
            logger.info(
                "MegaFon API accessible, %d users found. "
                "Configure webhook URL in MegaFon VATS cabinet: %s",
                len(users) if isinstance(users, list) else 0,
                connector.webhook_url,
            )
            return True
        except Exception as e:
            logger.warning(
                "MegaFon API check failed: %s. "
                "Webhook URL still generated: %s",
                e,
                connector.webhook_url,
            )
            return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """MegaFon webhook удаляется вручную в ЛК."""
        return {"ok": True}

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Инициация исходящего звонка через MegaFon VATS API.

        POST /crmapi/v1/makecall
        Body: {"phone": "79991234567", "user": "operator_login", "clid": "71117772211"}

        Args:
            connector: Коннектор MegaFon
            user_from: Контакт оператора (содержит логин/extension)
            body: Не используется для звонков
            chat_id: Номер телефона для звонка
            recipients_ids: Альтернативный способ передачи номера

        Returns:
            Tuple[callid, phone_number]
        """
        phone = chat_id
        if not phone and recipients_ids:
            phone = recipients_ids[0].get("contact_value")

        if not phone:
            raise ValueError("Cannot make call without phone number")

        # Определяем логин оператора из контакта
        operator_login = user_from.name if user_from else None
        if not operator_login:
            raise ValueError("Cannot make call without operator login")

        payload = {
            "phone": phone,
            "user": operator_login,
        }

        result = await self._api_request(
            connector, "/makecall", method="POST", json_data=payload
        )

        callid = ""
        if isinstance(result, dict):
            callid = result.get("callid", "")

        logger.info(
            "MegaFon makecall: %s → %s, callid=%s",
            operator_login,
            phone,
            callid,
        )

        return str(callid), str(phone)

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> MegafonPhoneAdapter:
        """Создать адаптер для webhook команды MegaFon."""
        return MegafonPhoneAdapter(connector, raw_message)

    # ========================================================================
    # Валидация webhook
    # ========================================================================

    def validate_webhook_token(
        self, connector: "ChatConnector", payload: dict
    ) -> bool:
        """
        Проверить crm_token во входящем webhook.

        MegaFon отправляет crm_token в теле каждого POST запроса.
        Сравниваем с vpbx_api_key на коннекторе.
        """
        crm_token = payload.get("crm_token", "")
        expected = connector.vpbx_api_key or ""
        return crm_token == expected

    # ========================================================================
    # MegaFon REST API — авторизованные запросы
    # ========================================================================

    def _get_headers(self, connector: "ChatConnector") -> dict:
        """Заголовки авторизации для запросов к MegaFon VATS API."""
        return {
            "X-API-KEY": connector.access_token or "",
            "Content-Type": "application/json",
        }

    async def _api_request(
        self,
        connector: "ChatConnector",
        path: str,
        method: str = "GET",
        params: dict | None = None,
        json_data: dict | None = None,
    ):
        """
        Выполнить авторизованный запрос к MegaFon VATS REST API.

        Args:
            connector: Коннектор с credentials
            path: Путь API (например '/users', '/history/json', '/makecall')
            method: HTTP метод
            params: URL query параметры
            json_data: JSON body для POST/PUT
        """
        base_url = (connector.connector_url or "").rstrip("/")
        url = f"{base_url}{path}"
        headers = self._get_headers(connector)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
            )

            if response.status_code == 401:
                raise ValueError(f"MegaFon VATS auth error: {response.text}")
            if response.status_code == 404:
                return {}

            if response.text:
                return response.json()
            return {}

    # ========================================================================
    # Скачивание записей разговоров
    # ========================================================================

    async def _download_call_record(
        self,
        connector: "ChatConnector",
        adapter: MegafonPhoneAdapter,
    ) -> bytes | None:
        """
        Скачать запись разговора по ссылке из history.

        MegaFon предоставляет прямую ссылку на MP3 файл
        в поле 'link' команды history.
        """
        record_url = adapter.call_record_url
        if not record_url:
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(record_url)
                if response.status_code == 200 and len(response.content) > 100:
                    return response.content
                logger.warning(
                    "[phone_megafon] Record download returned %d, %d bytes",
                    response.status_code,
                    len(response.content),
                )
        except Exception as e:
            logger.error("[phone_megafon] Failed to download record: %s", e)

        return None

    # ========================================================================
    # Пакетный импорт (cron)
    # ========================================================================

    async def fetch_call_history(
        self,
        connector: "ChatConnector",
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        """
        Получить историю звонков через MegaFon API.

        GET /crmapi/v1/history/json?start={from}&end={to}&type=all

        Args:
            connector: Коннектор
            date_from: Дата начала (формат: 20260101T000000Z)
            date_to: Дата конца (формат: 20260131T235959Z)

        Returns:
            Список звонков (dict)
        """
        params = {
            "start": date_from,
            "end": date_to,
            "type": "all",
            "limit": 1000,
        }
        result = await self._api_request(
            connector, "/history/json", params=params
        )

        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return []

    async def fetch_users(self, connector: "ChatConnector") -> list[dict]:
        """
        Получить список пользователей (операторов) из MegaFon VATS.

        GET /crmapi/v1/users

        Returns:
            Список пользователей с полями: login, name, telnum, ext, etc.
        """
        result = await self._api_request(connector, "/users")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return []

    async def make_call(
        self,
        connector: "ChatConnector",
        phone: str,
        user_login: str,
        clid: str | None = None,
    ) -> dict:
        """
        Инициировать исходящий звонок.

        POST /crmapi/v1/makecall

        Args:
            connector: Коннектор
            phone: Номер для звонка
            user_login: Логин оператора
            clid: Caller ID (какой номер показать клиенту)

        Returns:
            Ответ API: {"callid": "...", "clid": "..."}
        """
        payload = {"phone": phone, "user": user_login}
        if clid:
            payload["clid"] = clid

        result = await self._api_request(
            connector, "/makecall", method="POST", json_data=payload
        )
        return result if isinstance(result, dict) else {}
