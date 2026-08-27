"""
Unit-тесты выдачи ICE/TURN-конфига (backend/base/crm/chat/turn.py).

Проверяем ровно то, что ломает звонки молча:
- формат временных кредов (его должен принять coturn, а сверить нам не с чем,
  кроме самой формулы TURN REST API);
- деградацию, когда релей не настроен: ответ обязан оставаться валидным, иначе
  внутренние звонки перестанут собираться даже там, где раньше работали;
- разбор XOR-адреса из ответа сервера — на нём держится диагностика.

No database, no network. Pure function tests.

Run: pytest tests/unit/test_turn_credentials.py -v -m unit
"""

import base64
import hashlib
import hmac
import struct
import time

import pytest

from backend.base.crm.chat.settings import TurnSettings
from backend.base.crm.chat.turn import (
    _ATTR_MESSAGE_INTEGRITY,
    _CLASS_REQUEST,
    _METHOD_ALLOCATE,
    _attr,
    _is_response_to,
    host_from_request,
    resolve_settings,
    _pack,
    _parse_attrs,
    _with_integrity,
    _xor_address,
    build_ice_config,
    ensure_secret,
    load_secret,
    make_credentials,
    reset_secret_cache,
)

pytestmark = pytest.mark.unit


def _ready_settings(**kwargs) -> TurnSettings:
    return TurnSettings(
        enabled=True, host="turn.example.com", secret="s3cret", **kwargs
    )


class TestMakeCredentials:
    def test_username_is_expiry_and_user_id(self):
        username, _, expires_at = make_credentials("s3cret", 3600, 42)

        assert username == f"{expires_at}:42"
        # Срок в будущем, с поправкой на секунду между вызовами.
        assert expires_at - int(time.time()) == pytest.approx(3600, abs=2)

    def test_credential_is_hmac_sha1_of_username(self):
        username, credential, _ = make_credentials("s3cret", 3600, 7)

        expected = base64.b64encode(
            hmac.new(b"s3cret", username.encode(), hashlib.sha1).digest()
        ).decode()
        assert credential == expected

    def test_short_ttl_is_raised_to_minute(self):
        """Креды на 0 секунд протухнут раньше, чем браузер их применит."""
        _, _, expires_at = make_credentials("s3cret", 0, 1)

        assert expires_at - int(time.time()) >= 59


class TestBuildIceConfig:
    def test_turn_urls_cover_udp_and_tcp(self):
        config = build_ice_config(_ready_settings(), 42)

        urls = [
            url for server in config["ice_servers"] for url in server["urls"]
        ]
        assert "turn:turn.example.com:3478?transport=udp" in urls
        # TCP-плечо — единственное, что работает в сети с закрытым UDP.
        assert "turn:turn.example.com:3478?transport=tcp" in urls
        # turns: без сертификата не анонсируем.
        assert not any(url.startswith("turns:") for url in urls)

    def test_tls_url_added_when_port_set(self):
        config = build_ice_config(_ready_settings(tls_port=5349), 42)

        urls = [
            url for server in config["ice_servers"] for url in server["urls"]
        ]
        assert "turns:turn.example.com:5349?transport=tcp" in urls

    def test_stun_entry_has_no_credentials(self):
        """Смешивать stun: и turn: в одной записи браузеры не любят."""
        config = build_ice_config(_ready_settings(), 42)

        stun = config["ice_servers"][0]
        assert stun["urls"] == ["stun:turn.example.com:3478"]
        assert "username" not in stun

    def test_force_relay_switches_policy(self):
        config = build_ice_config(_ready_settings(force_relay=True), 42)

        assert config["ice_transport_policy"] == "relay"

    def test_disabled_falls_back_to_stun(self):
        config = build_ice_config(TurnSettings(enabled=False), 42)

        urls = [
            url for server in config["ice_servers"] for url in server["urls"]
        ]
        assert urls and all(url.startswith("stun:") for url in urls)
        assert config["ttl"] == 0

    def test_enabled_without_secret_does_not_hand_out_broken_creds(self):
        """Недонастроенный релей не должен выглядеть настроенным."""
        config = build_ice_config(
            TurnSettings(enabled=True, host="turn.example.com"), 42
        )

        assert not any(
            url.startswith("turn")
            for server in config["ice_servers"]
            for url in server["urls"]
        )

    def test_no_servers_at_all_is_valid(self):
        """Закрытый контур: ни релея, ни внешних STUN — ответ всё равно валиден."""
        config = build_ice_config(
            TurnSettings(enabled=False, fallback_stun=[]), 42
        )

        assert config["ice_servers"] == []
        assert config["ice_transport_policy"] == "all"


class TestIceConfigCredentials:
    """Отдельно от URL: без этих полей браузер молча не пойдёт через релей."""

    def test_turn_entry_carries_credentials(self):
        config = build_ice_config(_ready_settings(), 42)

        turn = [
            s
            for s in config["ice_servers"]
            if any(u.startswith("turn") for u in s["urls"])
        ]
        assert len(turn) == 1
        assert turn[0]["username"].endswith(":42")
        assert turn[0]["credential"]

    def test_ttl_matches_settings(self):
        config = build_ice_config(_ready_settings(ttl=1800), 42)

        assert config["ttl"] == pytest.approx(1800, abs=2)

    def test_fallback_stun_kept_when_relay_is_on(self):
        """Упавший релей не должен уносить с собой обычный p2p."""
        config = build_ice_config(_ready_settings(), 42)

        urls = [u for s in config["ice_servers"] for u in s["urls"]]
        assert "stun:stun.l.google.com:19302" in urls


class TestDefaults:
    def test_relay_is_on_by_default(self):
        """Релей едет в поставке — выключать его надо осознанно."""
        assert TurnSettings().enabled is True

    def test_enabled_without_host_still_answers(self):
        """Включён, но адрес не определился — ответ валиден, звонки живут."""
        config = build_ice_config(TurnSettings(secret="s3cret"), 42)

        assert config["ttl"] == 0
        assert all(
            url.startswith("stun:")
            for server in config["ice_servers"]
            for url in server["urls"]
        )


class TestSecretFile:
    def test_generated_once_and_reused(self, tmp_path):
        settings = TurnSettings(
            enabled=True,
            host="turn.example.com",
            secret_file=str(tmp_path / "secret"),
        )

        first = ensure_secret(settings)
        reset_secret_cache()
        second = ensure_secret(settings)

        assert first and first == second
        # Файл, созданный чужим процессом (второй uvicorn-воркер), не
        # перезаписывается — иначе половина выданных кредов стала бы неверной.
        assert (tmp_path / "secret").read_text().strip() == first

    def test_explicit_secret_wins(self, tmp_path):
        settings = TurnSettings(
            enabled=True,
            host="turn.example.com",
            secret="from-env",
            secret_file=str(tmp_path / "secret"),
        )

        assert ensure_secret(settings) == "from-env"
        assert not (tmp_path / "secret").exists()

    def test_missing_file_is_not_an_error(self, tmp_path):
        reset_secret_cache()
        settings = TurnSettings(
            enabled=True,
            host="turn.example.com",
            secret_file=str(tmp_path / "nope"),
        )

        assert load_secret(settings) == ""

    def test_config_from_file_secret(self, tmp_path):
        reset_secret_cache()
        path = tmp_path / "secret"
        path.write_text("abc123")
        settings = TurnSettings(
            enabled=True, host="turn.example.com", secret_file=str(path)
        )

        config = build_ice_config(settings, 7)

        username = config["ice_servers"][1]["username"]
        expected = base64.b64encode(
            hmac.new(b"abc123", username.encode(), hashlib.sha1).digest()
        ).decode()
        assert config["ice_servers"][1]["credential"] == expected


class TestMessageIntegrity:
    """
    Эти проверки ловят дефект, который в бою выглядит как «неверный секрет».

    Длину в заголовке нужно увеличить на размер MESSAGE-INTEGRITY И при
    подсчёте HMAC, И в отправляемом пакете: иначе сервер не видит атрибут за
    объявленной границей и вечно отвечает 401 при верном секрете.
    """

    def _allocate(self) -> tuple[bytes, bytes]:
        tid = b"\x01" * 12
        attrs = _attr(0x0019, struct.pack(">BBBB", 17, 0, 0, 0))
        return _pack(_METHOD_ALLOCATE, _CLASS_REQUEST, tid, attrs), tid

    def test_header_length_covers_the_attribute(self):
        message, _ = self._allocate()

        signed = _with_integrity(message, "user", "realm", "pass")

        declared = struct.unpack(">H", signed[2:4])[0]
        assert declared == len(signed) - 20

    def test_attribute_is_present_and_last(self):
        message, _ = self._allocate()

        signed = _with_integrity(message, "user", "realm", "pass")

        attrs = _parse_attrs(signed)
        assert _ATTR_MESSAGE_INTEGRITY in attrs
        assert len(attrs[_ATTR_MESSAGE_INTEGRITY]) == 20

    def test_hmac_uses_long_term_key(self):
        message, _ = self._allocate()

        signed = _with_integrity(message, "user", "realm", "pass")

        key = hashlib.md5(b"user:realm:pass", usedforsecurity=False).digest()
        body = signed[: -(20 + 4)]
        assert (
            _parse_attrs(signed)[_ATTR_MESSAGE_INTEGRITY]
            == hmac.new(key, body, hashlib.sha1).digest()
        )


class TestResponseMatching:
    def test_foreign_transaction_is_rejected(self):
        """Дубликат ответа на прошлый шаг не должен сойти за ответ на новый."""
        data = _pack(_METHOD_ALLOCATE, 0x0100, b"\x02" * 12, b"")

        assert _is_response_to(data, b"\x02" * 12)
        assert not _is_response_to(data, b"\x03" * 12)

    def test_garbage_is_rejected(self):
        assert not _is_response_to(b"\x00\x01", b"\x00" * 12)
        # Верный tid, но не STUN (нет magic cookie).
        assert not _is_response_to(b"\x00" * 8 + b"\x04" * 12, b"\x04" * 12)


class TestXorAddress:
    def test_ipv4_is_unxored(self):
        # 192.0.2.1:50000, закодированные как XOR-MAPPED-ADDRESS.
        magic = 0x2112A442
        port = 50000 ^ (magic >> 16)
        raw = bytes(
            b ^ m
            for b, m in zip(bytes((192, 0, 2, 1)), struct.pack(">I", magic))
        )
        value = struct.pack(">BBH", 0, 0x01, port) + raw

        assert _xor_address(value, b"\x00" * 12) == "192.0.2.1:50000"

    def test_truncated_value_does_not_raise(self):
        """Битый ответ не должен ронять проверку соединения."""
        assert _xor_address(b"\x00\x01", b"\x00" * 12) == ""


class TestHostFromRequest:
    """
    Домен запроса — последний рубеж «работает сразу после docker compose up»:
    если site_url не заполнен, адрес релея берётся отсюда.
    """

    class _Req:
        def __init__(self, **headers):
            self.headers = headers

    def test_forwarded_host_wins_over_internal(self):
        # За nginx собственный Host бэкенда — backend:8000, он бесполезен.
        req = self._Req(
            **{"x-forwarded-host": "crm.example.com", "host": "backend:8000"}
        )
        assert host_from_request(req) == "crm.example.com"

    def test_port_is_stripped(self):
        assert host_from_request(self._Req(host="crm.example.com:8443")) == (
            "crm.example.com"
        )

    def test_first_hop_of_forwarded_chain(self):
        req = self._Req(**{"x-forwarded-host": "a.example.com, b.example.com"})
        assert host_from_request(req) == "a.example.com"

    def test_ipv6_loses_brackets(self):
        assert host_from_request(self._Req(host="[2001:db8::1]:8000")) == (
            "2001:db8::1"
        )

    def test_no_headers_is_empty_not_error(self):
        assert host_from_request(self._Req()) == ""


class _FakeSettings:
    """Половина env.settings, которая нужна resolve_settings."""

    def __init__(self, turn):
        self.turn = turn
        self.site_url = ""


class _FakeModels:
    """system_settings, который отказывает в чтении — как в проде."""

    class system_settings:
        @staticmethod
        async def get_by_module(module):
            raise PermissionError("No read access to system_settings")

        @staticmethod
        async def get_site_url():
            raise PermissionError("No read access to system_settings")


class _FakeEnv:
    def __init__(self, turn):
        self.settings = _FakeSettings(turn)
        self.models = _FakeModels()


class TestResolveSettings:
    """
    Настройки могут быть недоступны — адрес релея от этого пропадать не должен.

    /ice/servers зовёт обычный сотрудник, а таблица system_settings ему
    закрыта (там же пароли SMTP). Раньше на этой ошибке стоял ранний выход, и
    вместе с настройками терялся резолв адреса: релей молча вырождался в
    «отдаём только STUN», хотя coturn был поднят и порты открыты.
    """

    async def test_host_falls_back_to_request_when_settings_unreadable(self):
        env = _FakeEnv(TurnSettings(host="", secret="s", secret_file=""))

        resolved = await resolve_settings(env, request_host="crm.example.com")

        assert resolved.host == "crm.example.com"

    async def test_explicit_host_is_not_overridden_by_request(self):
        env = _FakeEnv(TurnSettings(host="turn.example.com", secret="s"))

        resolved = await resolve_settings(env, request_host="crm.example.com")

        assert resolved.host == "turn.example.com"

    async def test_ice_config_gets_relay_after_fallback(self):
        """Сквозная проверка: адрес добрался до конфига для браузера."""
        env = _FakeEnv(TurnSettings(host="", secret="s", secret_file=""))

        resolved = await resolve_settings(env, request_host="crm.example.com")
        config = build_ice_config(resolved, user_id=7)

        urls = [
            url for entry in config["ice_servers"] for url in entry["urls"]
        ]
        assert any(url.startswith("turn:crm.example.com:") for url in urls)
        assert config["ttl"] > 0
