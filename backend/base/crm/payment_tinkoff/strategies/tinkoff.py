# Copyright 2025 FARA CRM
# Payment T-Bank module - провайдер T-Bank (Тинькофф) Acquiring API v2

import hashlib
import hmac
from typing import TYPE_CHECKING

import httpx

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import Decimal
from backend.base.crm.payment.strategies.provider import PaymentProviderBase

if TYPE_CHECKING:
    from backend.base.crm.payment.models.payment import Payment

DEFAULT_API_URL = "https://securepay.tinkoff.ru/v2/"
SETTING_TERMINAL_KEY = "payment_tinkoff.terminal_key"
SETTING_PASSWORD = "payment_tinkoff.password"
SETTING_API_URL = "payment_tinkoff.api_url"

# Статус платежа T-Bank → состояние нашего платежа. Остальные статусы
# (NEW, FORM_SHOWED, AUTHORIZING, 3DS_*, CONFIRMING) — промежуточные.
STATUS_MAP = {
    "CONFIRMED": "paid",
    "REJECTED": "failed",
    "CANCELED": "failed",
    "DEADLINE_EXPIRED": "failed",
    "AUTH_FAIL": "failed",
}


def kopecks(amount) -> int:
    """Сумма в копейках — так считает API банка."""
    return int((Decimal.to_decimal(amount) * 100).to_integral_value())


def _token_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def make_token(params: dict, password: str) -> str:
    """
    Подпись запроса и уведомления T-Bank.

    Скалярные параметры верхнего уровня + Password, сортировка по ключу,
    конкатенация значений, SHA-256. Вложенные объекты (Shops, DATA,
    Receipt) и сам Token в подписи не участвуют.
    """
    scalars = {
        key: value
        for key, value in params.items()
        if key != "Token" and not isinstance(value, (dict, list))
    }
    scalars["Password"] = password
    joined = "".join(_token_value(scalars[key]) for key in sorted(scalars))
    return hashlib.sha256(joined.encode()).hexdigest()


class TinkoffProvider(PaymentProviderBase):
    """
    T-Bank Acquiring API v2 с «Мультирасчётами»: в Init передаём Shops с
    кодом магазина получателя (payee_account = ShopCode) и Fee — комиссией
    площадки; банк сам делит поступление. Без ShopCode вся сумма
    зачисляется владельцу терминала.
    """

    provider_type = "tinkoff"
    TIMEOUT = 30

    async def create_payment(
        self, payment: "Payment", return_url: str
    ) -> tuple[str, str]:
        terminal_key, password, api_url = await self._settings()
        settings = env.models.system_settings
        site_url = (await settings.get_site_url()).rstrip("/")
        api_public_url = (await settings.get_api_url()).rstrip("/")

        amount = kopecks(payment.amount)
        params = {
            "TerminalKey": terminal_key,
            "Amount": amount,
            "OrderId": str(payment.id),
            "Description": (payment.description or "")[:250],
            "NotificationURL": (
                f"{api_public_url}/payments/webhook/{self.provider_type}"
            ),
            "SuccessURL": f"{site_url}{return_url}",
            "FailURL": f"{site_url}{return_url}",
        }
        if payment.payee_account:
            params["Shops"] = [
                {
                    "ShopCode": payment.payee_account,
                    "Amount": amount,
                    "Fee": kopecks(payment.commission_amount),
                    "Name": params["Description"],
                }
            ]
        params["Token"] = make_token(params, password)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                f"{api_url.rstrip('/')}/Init", json=params
            )
        data = response.json()
        if not data.get("Success"):
            raise FaraException(
                {
                    "content": "PAYMENT_TINKOFF_INIT_FAILED",
                    "detail": data.get("Details")
                    or data.get("Message")
                    or str(data),
                    "status_code": 400,
                }
            )
        return str(data["PaymentId"]), data["PaymentURL"]

    async def handle_notification(
        self, payload: dict
    ) -> tuple[str, str | None]:
        _, password, _ = await self._settings()
        token = str(payload.get("Token") or "")
        if not hmac.compare_digest(
            token.encode(), make_token(payload, password).encode()
        ):
            raise FaraException(
                {
                    "content": "PAYMENT_TINKOFF_BAD_TOKEN",
                    "detail": "Неверная подпись уведомления",
                    "status_code": 403,
                }
            )
        return (
            str(payload.get("PaymentId")),
            STATUS_MAP.get(str(payload.get("Status"))),
        )

    @staticmethod
    async def _settings() -> tuple[str, str, str]:
        settings = env.models.system_settings
        terminal_key = await settings.get_value(SETTING_TERMINAL_KEY, "")
        password = await settings.get_value(SETTING_PASSWORD, "")
        api_url = (
            await settings.get_value(SETTING_API_URL, DEFAULT_API_URL)
            or DEFAULT_API_URL
        )
        if not terminal_key or not password:
            raise FaraException(
                {
                    "content": "PAYMENT_TINKOFF_NOT_CONFIGURED",
                    "detail": (
                        "Укажите TerminalKey и пароль T-Bank в системных "
                        "настройках"
                    ),
                    "status_code": 400,
                }
            )
        return terminal_key, password, api_url
