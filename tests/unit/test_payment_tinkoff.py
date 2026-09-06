"""
Unit-тесты подписи и маппинга статусов провайдера T-Bank
(backend/base/crm/payment_tinkoff/strategies/tinkoff.py).

Проверяем то, что при ошибке молча ломает оплату:
- формулу подписи: сортировка по ключу, Password внутри, Token и вложенные
  объекты (Shops) снаружи, булевы значения строчными — иначе банк отвергнет
  Init, а мы отвергнем его уведомление;
- перевод суммы в копейки без потери копеек на float;
- какие статусы банка закрывают платёж.

No database, no network. Pure function tests.

Run: pytest tests/unit/test_payment_tinkoff.py -v -m unit
"""

import hashlib
from decimal import Decimal

import pytest

from backend.base.crm.payment_tinkoff.strategies.tinkoff import (
    STATUS_MAP,
    kopecks,
    make_token,
)

pytestmark = pytest.mark.unit


class TestMakeToken:
    def test_sorted_values_with_password(self):
        params = {
            "TerminalKey": "MerchantTerminalKey",
            "Amount": 19200,
            "OrderId": "21090",
            "Description": "Подарочная карта на 1000 рублей",
        }

        expected = hashlib.sha256(
            (
                "19200"
                "Подарочная карта на 1000 рублей"
                "21090"
                "usaf8fw8fsfwqasdqwa"
                "MerchantTerminalKey"
            ).encode()
        ).hexdigest()
        assert make_token(params, "usaf8fw8fsfwqasdqwa") == expected

    def test_nested_objects_and_token_are_ignored(self):
        """Shops/DATA не подписываются; свой Token из уведомления — тоже."""
        base = {"TerminalKey": "t", "Amount": 100, "OrderId": "1"}
        extended = {
            **base,
            "Shops": [{"ShopCode": "s1", "Amount": 100}],
            "DATA": {"Email": "a@b.c"},
            "Token": "stale",
        }

        assert make_token(extended, "pw") == make_token(base, "pw")

    def test_booleans_are_lowercase_strings(self):
        """Success=true из уведомления банка подписан именно как «true»."""
        params = {"Success": True, "Amount": 1}

        expected = hashlib.sha256("1pwtrue".encode()).hexdigest()
        assert make_token(params, "pw") == expected


class TestKopecks:
    def test_decimal_rubles_to_kopecks(self):
        assert kopecks(Decimal("1234.56")) == 123456

    def test_float_does_not_lose_kopeck(self):
        # 0.29 * 100 во float = 28.999…; целочисленное округление обязано
        # дать 29.
        assert kopecks(0.29) == 29

    def test_unset_amount_is_zero(self):
        assert kopecks(None) == 0


class TestStatusMap:
    def test_only_confirmed_is_paid(self):
        assert STATUS_MAP["CONFIRMED"] == "paid"
        assert "AUTHORIZED" not in STATUS_MAP

    def test_final_failures_close_payment(self):
        for status in (
            "REJECTED",
            "CANCELED",
            "DEADLINE_EXPIRED",
            "AUTH_FAIL",
        ):
            assert STATUS_MAP[status] == "failed"

    def test_intermediate_statuses_are_ignored(self):
        assert STATUS_MAP.get("NEW") is None
        assert STATUS_MAP.get("FORM_SHOWED") is None
