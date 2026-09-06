# Copyright 2025 FARA CRM
# Payment module - базовый платёжный провайдер

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.payment.models.payment import Payment


class PaymentProviderBase:
    """
    Провайдер онлайн-оплаты (T-Bank, Сбер, …) — отдельный модуль на каждого.

    Провайдер отвечает за два шага: создать платёж и получить ссылку на
    оплату, разобрать уведомление о результате (обязательно сверив подпись).
    Что делать с оплаченной записью — решает модель Payment.
    """

    provider_type: str = ""
    # Что ответить провайдеру на уведомление, чтобы он перестал его слать.
    notification_response: str = "OK"

    async def create_payment(
        self, payment: "Payment", return_url: str
    ) -> tuple[str, str]:
        """Создать платёж у провайдера → (external_id, payment_url).

        return_url — относительный путь на сайте, куда вернуть плательщика.
        """
        raise NotImplementedError

    async def handle_notification(
        self, payload: dict
    ) -> tuple[str, str | None]:
        """Разобрать уведомление → (external_id, "paid" | "failed" | None).

        None — промежуточный статус, платёж не трогаем.
        """
        raise NotImplementedError
