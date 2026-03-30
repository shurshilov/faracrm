# Copyright 2025 FARA CRM
# Chat Phone Sipuni module - Sipuni strategy

import csv
import io
import logging
from hashlib import md5
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat_phone.strategies.strategy import PhoneStrategyBase
from .adapter import SipuniPhoneAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.partners.models.contact import Contact

logger = logging.getLogger(__name__)


class SipuniPhoneStrategy(PhoneStrategyBase):
    """
    Стратегия для интеграции с Sipuni (sipuni.com).

    API документация: https://sipuni.com/ru_RU/integration

    Поддерживает:
    - Приём событий звонков через webhook (event 1/2/3)
    - Получение истории звонков через API
    - Скачивание записей разговоров
    - Получение списка операторов/номеров

    Авторизация: login + password → HMAC MD5 подпись.
    """

    strategy_type = "phone_sipuni"
    TIMEOUT = 30.0

    # ========================================================================
    # Абстрактные методы ChatStrategyBase
    # ========================================================================

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """Sipuni использует login/password, токен не нужен."""
        return None

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Sipuni не имеет API для установки webhook.
        Webhook URL настраивается вручную в личном кабинете Sipuni.

        Возвращаем True — URL уже сгенерирован.
        """
        logger.info(
            "Sipuni webhook URL generated: %s. "
            "Configure it manually in Sipuni dashboard.",
            connector.webhook_url,
        )
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """Sipuni webhook удаляется вручную в ЛК."""
        return {"ok": True}

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """Sipuni не поддерживает инициацию звонков через API."""
        raise NotImplementedError(
            "Sipuni does not support initiating calls via API"
        )

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> SipuniPhoneAdapter:
        """Создать адаптер для webhook события Sipuni."""
        return SipuniPhoneAdapter(connector, raw_message)

    # ========================================================================
    # Sipuni API — авторизация и запросы
    # ========================================================================

    def _build_sign(self, connector: "ChatConnector", params: dict) -> str:
        """
        Построить HMAC MD5 подпись для API запроса Sipuni.

        Алгоритм:
        1. Добавить user= в params
        2. Сортировать ключи
        3. Склеить значения через '+'
        4. Добавить пароль в конец
        5. MD5 хеш
        """
        params["user"] = connector.access_token or connector.client_app_id
        sorted_values = [str(params[key]) for key in sorted(params.keys())]
        data = "+".join([*sorted_values, connector.refresh_token or ""])
        return md5(data.encode("utf-8")).hexdigest()

    async def _api_request(
        self,
        connector: "ChatConnector",
        path: str,
        params: dict | None = None,
        binary: bool = False,
        csv_content: bool = False,
        csv_fields: list[str] | None = None,
    ):
        """
        Выполнить авторизованный запрос к API Sipuni.

        Args:
            connector: Коннектор с credentials
            path: Путь API (например '/statistic/export')
            params: Параметры запроса
            binary: Вернуть bytes (для скачивания файлов)
            csv_content: Парсить ответ как CSV
            csv_fields: Названия колонок CSV
        """
        params = params or {}
        sign = self._build_sign(connector, params)

        data = {"hash": sign}
        data.update(params)

        base_url = connector.connector_url or "https://sipuni.com/api"
        url = f"{base_url}{path}"

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, data=data)

            if response.status_code == 401:
                raise ValueError(f"Sipuni auth error: {response.text}")
            if response.status_code == 404:
                return {} if not csv_content else []

            if binary:
                return response.content

            if csv_content:
                return self._parse_csv(response.text, csv_fields or [])

            return response.json() if response.text else []

    @staticmethod
    def _parse_csv(text: str, fields: list[str]) -> list[dict]:
        """Парсинг CSV ответа Sipuni."""
        data_file = io.StringIO(text)
        reader = csv.reader(data_file, delimiter=";")
        rows = list(reader)

        if len(rows) <= 1:
            return []

        # Используем переданные fields как ключи
        result = []
        for row in rows[1:]:
            # Расширяем fields если в CSV больше колонок
            keys = fields[:]
            while len(keys) < len(row):
                keys.append(f"col_{len(keys)}")
            result.append(dict(zip(keys, row)))

        return result

    # ========================================================================
    # Скачивание записей разговоров
    # ========================================================================

    async def _download_call_record(
        self,
        connector: "ChatConnector",
        adapter: SipuniPhoneAdapter,
    ) -> bytes | None:
        """
        Скачать запись разговора через Sipuni API.

        Sipuni предоставляет call_record_link — прямой URL на запись.
        Но также есть API endpoint /statistic/record.
        Используем call_record_link если доступен, иначе API.
        """
        # Вариант 1: прямая ссылка из webhook
        record_link = adapter.call_record_url
        if record_link:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(record_link)
                    if response.status_code == 200 and response.content:
                        return response.content
            except Exception as e:
                logger.warning(
                    "[phone_sipuni] Direct download failed: %s, trying API",
                    e,
                )

        # Вариант 2: через API
        call_id = adapter.message_id
        if call_id:
            try:
                content = await self._api_request(
                    connector,
                    "/statistic/record",
                    params={"id": call_id},
                    binary=True,
                )
                if content and len(content) > 100:  # Минимальный размер MP3
                    return content
            except Exception as e:
                logger.error(
                    "[phone_sipuni] API download failed for %s: %s",
                    call_id,
                    e,
                )

        return None

    # ========================================================================
    # Пакетный импорт звонков (cron)
    # ========================================================================

    async def fetch_call_history(
        self,
        connector: "ChatConnector",
        date_from: str,
        date_to: str,
        time_from: str = "",
        time_to: str = "",
    ) -> list[dict]:
        """
        Получить историю звонков через API Sipuni.

        Args:
            connector: Коннектор
            date_from: Дата начала (DD.MM.YYYY)
            date_to: Дата конца (DD.MM.YYYY)
            time_from: Время начала (HH:MM)
            time_to: Время конца (HH:MM)

        Returns:
            Список звонков (dict)
        """
        params = {
            "from": date_from,
            "to": date_to,
            "timeFrom": time_from,
            "timeTo": time_to,
            "type": "0",  # Все звонки
            "state": "0",  # Все статусы
            "tree": "",
            "rating": "",
            "showTreeId": "1",
            "fromNumber": "",
            "toNumber": "",
            "numbersRinged": 1,
            "numbersInvolved": 1,
            "names": 1,
            "outgoingLine": 1,
            "toAnswer": "",
            "anonymous": "0",
            "firstTime": "0",
            "dtmfUserAnswer": 0,
            "hangupinitor": "1",
            "crmLinks": 0,
            "ignoreSpecChar": "0",
        }

        csv_fields = [
            "Тип",
            "Статус",
            "Время",
            "ID схемы звонка",
            "Схема",
            "Исходящая линия",
            "Откуда",
            "Куда",
            "Кому звонили",
            "Кто разговаривал",
            "Кто ответил",
            "Длительность звонка, сек",
            "Длительность разговора, сек",
            "Время ответа, сек",
            "Оценка",
            "ID записи",
            "Метка",
            "Теги",
            "Инициатор завершения звонка",
            "ID заказа звонка",
            "Запись существует",
            "Новый клиент",
            "Состояние перезвона",
            "Время перезвона",
            "Информация из CRM",
            "Ответственный из CRM",
        ]

        return await self._api_request(
            connector,
            "/statistic/export",
            params=params,
            csv_content=True,
            csv_fields=csv_fields,
        )

    async def fetch_operators(self, connector: "ChatConnector") -> list[dict]:
        """
        Получить список операторов (внутренних номеров) из Sipuni.

        Returns:
            Список операторов с полями: Login, Name, Status, Call state
        """
        return await self._api_request(
            connector,
            "/statistic/operators",
            csv_content=True,
            csv_fields=["Login", "Name", "Status", "Call state"],
        )
