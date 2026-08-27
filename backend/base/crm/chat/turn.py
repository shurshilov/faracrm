# Copyright 2025 FARA CRM
# Chat module - ICE/TURN: секрет, выдача кредов и проверка релея
#
# Здесь НЕТ ORM и FastAPI — только протокол, настройки и файл секрета. Так эту
# логику можно звать и из роутера, и из тестов, не поднимая окружение.
#
# Схема кредов — TURN REST API (RFC 7635), её понимают coturn и любой другой
# сервер с общим секретом:
#     username   = "<unixtime истечения>:<user_id>"
#     credential = base64( HMAC-SHA1( secret, username ) )
# Сервер релея проверяет подпись и срок сам, база пользователей ему не нужна:
# заводить/удалять сотрудников на нём не приходится.

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import secrets
import socket
import struct
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.chat.settings import TurnSettings

logger = logging.getLogger(__name__)

# ─── STUN/TURN константы (RFC 5389 / RFC 8656) ────────────────────
_MAGIC_COOKIE = 0x2112A442
_METHOD_BINDING = 0x0001
_METHOD_ALLOCATE = 0x0003
_METHOD_REFRESH = 0x0004
_CLASS_REQUEST = 0x0000
_CLASS_ERROR = 0x0110

_ATTR_USERNAME = 0x0006
_ATTR_MESSAGE_INTEGRITY = 0x0008
_ATTR_ERROR_CODE = 0x0009
_ATTR_REALM = 0x0014
_ATTR_NONCE = 0x0015
_ATTR_XOR_RELAYED_ADDRESS = 0x0016
_ATTR_REQUESTED_TRANSPORT = 0x0019
_ATTR_XOR_MAPPED_ADDRESS = 0x0020
_ATTR_LIFETIME = 0x000D

_TRANSPORT_UDP = 17

# Аллокация для проверки живёт ровно столько, сколько нужно, чтобы получить
# ответ. Мы её ещё и снимаем явно (см. probe), но если снять не удалось —
# короткий срок не даст занятым портам копиться.
_PROBE_LIFETIME = 60


# ─── Секрет ───────────────────────────────────────────────────────
#
# Секрет обязан совпадать у нас и у сервера релея. Передавать его через
# переменную окружения плохо: docker compose подставляет переменные при
# СОЗДАНИИ контейнера, значит любое изменение требует пересоздания обоих
# сервисов, а опечатка в регистре имени переменной даёт молча пустой секрет и
# релей, который отвергает всё. Поэтому носитель — файл в общем томе, который
# оба процесса читают в рантайме.

_secret_cache: str | None = None

# О чём уже предупреждали в лог (см. build_ice_config).
_warned: set[str] = set()


def load_secret(settings: "TurnSettings") -> str:
    """
    Действующий секрет: явный из окружения, иначе из общего файла.

    Файл не создаём — только читаем: генерация это разовое действие при старте
    приложения (ensure_secret), а обработчик запроса не должен уметь писать
    в общий том.
    """
    global _secret_cache

    if settings.secret:
        return settings.secret
    if _secret_cache:
        return _secret_cache
    if not settings.secret_file:
        return ""

    try:
        with open(settings.secret_file, encoding="ascii") as handle:
            _secret_cache = handle.read().strip()
    except OSError:
        return ""
    return _secret_cache or ""


def ensure_secret(settings: "TurnSettings") -> str:
    """
    Секрет для релея, создавая его при первом запуске.

    Пишем через O_EXCL: если файл уже создал другой процесс (второй uvicorn-
    воркер или предыдущий запуск), запись просто не состоится и мы прочитаем
    чужой. Без этого два воркера стартуют одновременно и записывают РАЗНЫЕ
    секреты — половина выданных кредов оказалась бы невалидной.
    """
    global _secret_cache

    if settings.secret:
        return settings.secret
    if not settings.secret_file:
        return ""

    existing = load_secret(settings)
    if existing:
        return existing

    value = secrets.token_hex(32)
    try:
        os.makedirs(
            os.path.dirname(settings.secret_file) or ".", exist_ok=True
        )
        # 0644, а не 0600: файл лежит в томе, общем с контейнером релея, а тот
        # работает не от root. Том больше никуда не подключён, так что «читают
        # все» здесь означает «читают эти два контейнера».
        handle = os.open(
            settings.secret_file,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
        with os.fdopen(handle, "w", encoding="ascii") as file:
            file.write(value)
        _secret_cache = value
        logger.info("[turn] секрет релея создан: %s", settings.secret_file)
        return value
    except FileExistsError:
        # Кто-то опередил — читаем то, что записал он.
        _secret_cache = None
        return load_secret(settings)
    except OSError as exc:
        logger.warning(
            "[turn] не удалось записать секрет в %s: %s",
            settings.secret_file,
            exc,
        )
        return ""


def reset_secret_cache() -> None:
    """Сбросить кеш секрета (нужно только тестам и ротации)."""
    global _secret_cache
    _secret_cache = None
    _warned.clear()


# ─── Креды и конфиг для браузера ──────────────────────────────────


def make_credentials(
    secret: str, ttl: int, user_id: int
) -> tuple[str, str, int]:
    """
    Выдать временные креды TURN.

    Возвращает (username, credential, expires_at). user_id идёт в username
    открытым текстом — это не секрет, зато в логах релея видно, чья аллокация.
    """
    expires_at = int(time.time()) + max(ttl, 60)
    username = f"{expires_at}:{user_id}"
    digest = hmac.new(
        secret.encode("utf-8"), username.encode("utf-8"), hashlib.sha1
    ).digest()
    return username, base64.b64encode(digest).decode("ascii"), expires_at


def build_ice_config(settings: "TurnSettings", user_id: int) -> dict:
    """
    Конфиг ICE для одного пользователя — ровно в форме RTCConfiguration.

    Отдаём ВСЕ транспорты сразу (udp/tcp/tls): браузер сам переберёт их и
    возьмёт первый рабочий. Именно tcp/tls спасают в корпоративных сетях,
    где UDP наружу закрыт — а таких у клиентов заметная доля.
    """
    ice_servers: list[dict] = []
    secret = load_secret(settings)
    ready = bool(settings.enabled and settings.host and secret)

    if not ready:
        if settings.enabled:
            # Включили, но не донастроили — молчать нельзя, звонки будут
            # «иногда не соединяться», и никто не поймёт почему. Но и писать
            # на КАЖДЫЙ запрос не стоит: релей включён по умолчанию, и на
            # стенде без него лог превратился бы в шум.
            missing = "адрес релея" if not settings.host else "секрет релея"
            if missing not in _warned:
                _warned.add(missing)
                logger.warning(
                    "TURN включён, но не определён %s — отдаём только STUN",
                    missing,
                )
        if settings.fallback_stun:
            ice_servers.append({"urls": list(settings.fallback_stun)})
        return {
            "ice_servers": ice_servers,
            "ice_transport_policy": "all",
            "ttl": 0,
        }

    username, credential, expires_at = make_credentials(
        secret, settings.ttl, user_id
    )

    host = settings.host
    urls = [
        f"turn:{host}:{settings.port}?transport=udp",
        f"turn:{host}:{settings.port}?transport=tcp",
    ]
    if settings.tls_port:
        urls.append(f"turns:{host}:{settings.tls_port}?transport=tcp")

    # STUN-адрес отдельной записью без кредов: браузеры не любят, когда в одном
    # объекте смешаны stun: и turn:, а srflx-кандидат нужен и без релея.
    ice_servers.append({"urls": [f"stun:{host}:{settings.port}"]})
    ice_servers.append(
        {"urls": urls, "username": username, "credential": credential}
    )
    # Запасные STUN оставляем и при работающем релее: если контейнер релея
    # упал, а CRM жива, p2p в дружественных сетях продолжит собираться. Кому
    # внешние адреса не нужны (закрытый контур) — очищает fallback_stun.
    if settings.fallback_stun:
        ice_servers.append({"urls": list(settings.fallback_stun)})

    return {
        "ice_servers": ice_servers,
        "ice_transport_policy": "relay" if settings.force_relay else "all",
        # Фронт по ttl понимает, когда перезапросить креды.
        "ttl": max(expires_at - int(time.time()), 0),
    }


# ─── Действующие настройки: .env как дефолт, интерфейс сверху ─────


_LOOPBACK = ("127.0.0.1", "localhost", "::1")


def host_from_request(req) -> str:
    """
    Домен, по которому браузер достучался до CRM.

    За прокси собственный Host бэкенда — это `backend:8000`, поэтому сначала
    смотрим X-Forwarded-Host (его ставит nginx, см. docker/nginx.conf).
    Порт и скобки IPv6 отбрасываем: у релея порт свой.
    """
    from urllib.parse import urlsplit

    forwarded = (req.headers.get("x-forwarded-host") or "").split(",")[0]
    raw = forwarded.strip() or req.headers.get("host") or ""
    try:
        return urlsplit(f"//{raw}").hostname or ""
    except ValueError:
        return ""


async def resolve_settings(env, request_host: str = "") -> "TurnSettings":
    """
    Настройки релея с учётом того, что задано в интерфейсе.

    Значения из .env — дефолт, строки системных настроек (модуль "turn") их
    перекрывают. Читаем ОДНИМ запросом и без кеша: кеш system_settings живёт
    в процессе, а воркеров несколько — закешированное значение расходилось бы
    между ними до перезапуска, и админ видел бы «настройка применилась через
    раз». Запрос делается на старте звонка, одна индексная строка — незаметно.

    Секрет через интерфейс не переопределяется (см. TurnSettings.UI_KEYS).
    """
    base = env.settings.turn

    overrides: dict = {}
    for row in await _read_overrides(env):
        key = (row.key or "").split(".", 1)[-1]
        if key not in base.UI_KEYS:
            continue
        raw = row.value
        value = raw.get("value") if isinstance(raw, dict) else raw
        # None = «не задано, берём из .env». Пустую строку трактуем так же:
        # в generic-форме очистить поле проще, чем удалить строку настройки.
        if value is None or value == "":
            continue
        overrides[key] = value

    # Адрес релея по умолчанию = домен CRM: релей стоит на той же машине, и
    # заставлять админа писать его второй раз незачем. Берём из системных
    # настроек (core.site_url), а не из .env: там он и правится.
    if not overrides.get("host") and not base.host:
        host = await _host_from_site_url(env)
        # site_url не заполнен или остался дефолтным localhost — берём домен,
        # по которому пришёл сам запрос. Браузер только что успешно достучался
        # по нему до CRM, а релей стоит на той же машине, так что после
        # `docker compose up` звонки работают без единой настройки.
        if (not host or host in _LOOPBACK) and request_host:
            host = request_host
        if host in _LOOPBACK and "loopback" not in _warned:
            _warned.add("loopback")
            logger.warning(
                "[turn] адрес релея — localhost (%s). Для рабочего стенда "
                "задайте site_url или TURN__HOST",
                host,
            )
        if host:
            overrides["host"] = host

    if not overrides:
        return base

    try:
        return type(base)(**{**base.model_dump(), **overrides})
    except Exception as exc:  # noqa: BLE001
        # Админ ввёл «3478 » или true/false строкой — это не повод уронить
        # звонки: работаем на .env и говорим, что именно не приняли.
        logger.warning(
            "[turn] системные настройки не приняты (%s), работаем на .env: %s",
            ", ".join(sorted(overrides)),
            exc,
        )
        return base


async def _read_overrides(env) -> list:
    """
    Прочитать строки настроек turn.* — НЕ от имени текущего пользователя.

    /ice/servers зовёт обычный сотрудник, а таблица system_settings ему
    закрыта, и правильно: там же лежат пароли SMTP и токены. Но конфиг релея
    это не пользовательские данные, а параметры соединения, которые всё равно
    уедут в браузер. Поэтому читаем под системной сессией и сразу возвращаем
    прежнюю.

    Сбой чтения не должен стоить нам адреса релея: возвращаем пустой список,
    и вызывающий доберёт host из site_url или домена запроса. Раньше здесь
    был ранний выход, и вместе с настройками терялся резолв адреса — релей
    молча вырождался в «отдаём только STUN».
    """
    try:
        return await env.models.system_settings.sudo().get_by_module("turn")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[turn] настройки из БД не прочитаны: %s", exc)
        return []


async def _host_from_site_url(env) -> str:
    """
    Домен, на котором открывают CRM, — он же адрес релея по умолчанию.

    Только имя хоста: схема и порт у релея свои. Localhost отдаём как есть —
    решение, годится ли он, принимает resolve_settings: там же есть запасной
    вариант в виде домена текущего запроса.
    """
    from urllib.parse import urlparse

    try:
        site_url = await env.models.system_settings.sudo().get_site_url()
    except Exception:  # noqa: BLE001
        site_url = getattr(env.settings, "site_url", "")

    try:
        return urlparse(site_url or "").hostname or ""
    except ValueError:
        return ""


# ─── Диагностика: реально ли работает релей ───────────────────────
#
# Клиент STUN/TURN на голых сокетах, без новых зависимостей. Нужен ровно для
# кнопки «Проверить релей»: без неё настройка превращается в гадание «то ли
# порт закрыт, то ли секрет не тот».


def _pack(method: int, cls: int, tid: bytes, attrs: bytes) -> bytes:
    return (
        struct.pack(">HHI", method | cls, len(attrs), _MAGIC_COOKIE)
        + tid
        + attrs
    )


def _attr(kind: int, value: bytes) -> bytes:
    pad = (-len(value)) % 4
    return struct.pack(">HH", kind, len(value)) + value + b"\x00" * pad


def _parse_attrs(data: bytes) -> dict[int, bytes]:
    """Разобрать атрибуты ответа. Дубли не нужны — берём первый."""
    attrs: dict[int, bytes] = {}
    offset = 20
    while offset + 4 <= len(data):
        kind, length = struct.unpack(">HH", data[offset : offset + 4])
        value = data[offset + 4 : offset + 4 + length]
        attrs.setdefault(kind, value)
        offset += 4 + length + ((-length) % 4)
    return attrs


def _with_integrity(
    message: bytes, username: str, realm: str, password: str
) -> bytes:
    """
    Дописать MESSAGE-INTEGRITY (long-term credentials).

    Тонкость протокола: длина в заголовке должна учитывать сам атрибут
    (20 байт значения + 4 заголовка) — И при подсчёте HMAC, И в том, что мы
    отправим. Посчитать по одной длине, а отправить с другой — получить вечный
    401 при верном секрете: сервер просто не увидит атрибут за границей длины.
    """
    key = hashlib.md5(
        f"{username}:{realm}:{password}".encode("utf-8"),
        usedforsecurity=False,
    ).digest()
    length = struct.unpack(">H", message[2:4])[0] + 24
    prepared = message[:2] + struct.pack(">H", length) + message[4:]
    digest = hmac.new(key, prepared, hashlib.sha1).digest()
    return prepared + _attr(_ATTR_MESSAGE_INTEGRITY, digest)


def _xor_address(value: bytes, tid: bytes) -> str:
    """XOR-MAPPED/RELAYED-ADDRESS → 'ip:port'."""
    if len(value) < 8:
        return ""
    family = value[1]
    port = struct.unpack(">H", value[2:4])[0] ^ (_MAGIC_COOKIE >> 16)
    if family == 0x01:
        raw = bytes(
            b ^ m for b, m in zip(value[4:8], struct.pack(">I", _MAGIC_COOKIE))
        )
        return f"{socket.inet_ntop(socket.AF_INET, raw)}:{port}"
    if len(value) < 20:
        return ""
    mask = struct.pack(">I", _MAGIC_COOKIE) + tid
    raw = bytes(b ^ m for b, m in zip(value[4:20], mask))
    return f"[{socket.inet_ntop(socket.AF_INET6, raw)}]:{port}"


class _StunClient(asyncio.DatagramProtocol):
    """Складывает всё пришедшее в очередь; отбор по tid делает вызывающий."""

    def __init__(self) -> None:
        self.responses: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr) -> None:
        self.responses.put_nowait(data)


def _is_response_to(data: bytes, tid: bytes) -> bool:
    """
    Ответ ли это на НАШ запрос.

    Без этой проверки дубликат ответа на предыдущий шаг (UDP дублирует пакеты
    штатно) съедается следующим шагом, и проверка врёт: например показывает
    «не совпадает секрет», когда секрет верный.
    """
    return (
        len(data) >= 20
        and data[4:8] == struct.pack(">I", _MAGIC_COOKIE)
        and data[8:20] == tid
    )


async def probe(settings: "TurnSettings", timeout: float = 3.0) -> dict:
    """
    Проверить релей вживую: Binding, затем Allocate с временными кредами.

    Возвращает {"ok", "error", "mapped_address", "relayed_address"}.
    Проверяем ТОЛЬКО UDP-плечо: если оно живо, значит адрес, порт и секрет
    верны — а доступность tcp/tls определяется сетью клиента, не нашей.

    Запрос идёт с сервера, а не из браузера пользователя: положительный ответ
    доказывает, что релей работает и секрет совпадает, но не проверяет путь
    от конкретного клиента.
    """
    result = {
        "ok": False,
        "error": "",
        "mapped_address": "",
        "relayed_address": "",
    }
    secret = load_secret(settings)
    if not (settings.enabled and settings.host and secret):
        result["error"] = "TURN не настроен (нужны адрес релея и секрет)"
        return result

    username, password, _ = make_credentials(secret, 300, 0)
    loop = asyncio.get_running_loop()
    # Чтобы отличить «сервер молчит» от «сервер есть, но это не TURN».
    answered = False

    try:
        transport, protocol = await loop.create_datagram_endpoint(
            _StunClient, remote_addr=(settings.host, settings.port)
        )
    except OSError as exc:
        result["error"] = f"Не удалось открыть сокет: {exc}"
        return result

    async def exchange(payload: bytes, tid: bytes, attempts: int = 2) -> bytes:
        """
        Отправить запрос и дождаться ответа ИМЕННО на него.

        Один ретрай обязателен: UDP теряет пакеты, а без повтора единственная
        потеря превращается в вердикт «релей не работает» на исправном релее.
        """
        for _ in range(attempts):
            transport.sendto(payload)
            deadline = loop.time() + timeout
            while True:
                left = deadline - loop.time()
                if left <= 0:
                    break
                try:
                    data = await asyncio.wait_for(
                        protocol.responses.get(), left
                    )
                except asyncio.TimeoutError:
                    break
                if _is_response_to(data, tid):
                    return data
        raise asyncio.TimeoutError

    realm = ""
    nonce = b""
    try:
        # 1. Binding — сервер вообще отвечает? Заодно узнаём свой внешний адрес.
        tid = os.urandom(12)
        data = await exchange(
            _pack(_METHOD_BINDING, _CLASS_REQUEST, tid, b""), tid
        )
        answered = True
        mapped = _parse_attrs(data).get(_ATTR_XOR_MAPPED_ADDRESS)
        if mapped:
            result["mapped_address"] = _xor_address(mapped, tid)

        # 2. Allocate без кредов — сервер обязан ответить 401 с realm и nonce.
        tid = os.urandom(12)
        request = _attr(
            _ATTR_REQUESTED_TRANSPORT,
            struct.pack(">BBBB", _TRANSPORT_UDP, 0, 0, 0),
        ) + _attr(_ATTR_LIFETIME, struct.pack(">I", _PROBE_LIFETIME))
        data = await exchange(
            _pack(_METHOD_ALLOCATE, _CLASS_REQUEST, tid, request), tid
        )
        attrs = _parse_attrs(data)
        realm = attrs.get(_ATTR_REALM, b"").decode("utf-8", "replace")
        nonce = attrs.get(_ATTR_NONCE, b"")
        if not realm or not nonce:
            result["error"] = (
                "Сервер ответил, но не запросил авторизацию — "
                "это не TURN или на нём выключен long-term credentials"
            )
            return result

        # 3. Allocate с подписью.
        tid = os.urandom(12)
        attrs_out = (
            request
            + _attr(_ATTR_USERNAME, username.encode("utf-8"))
            + _attr(_ATTR_REALM, realm.encode("utf-8"))
            + _attr(_ATTR_NONCE, nonce)
        )
        message = _pack(_METHOD_ALLOCATE, _CLASS_REQUEST, tid, attrs_out)
        data = await exchange(
            _with_integrity(message, username, realm, password), tid
        )
        attrs = _parse_attrs(data)
        kind = struct.unpack(">H", data[0:2])[0]

        if (kind & _CLASS_ERROR) == _CLASS_ERROR:
            code = attrs.get(_ATTR_ERROR_CODE, b"\x00\x00\x00\x00")
            number = code[2] * 100 + code[3] if len(code) >= 4 else 0
            reason = code[4:].decode("utf-8", "replace")
            result["error"] = (
                f"Релей отклонил аллокацию: {number} {reason}"
                + (" — не совпадает секрет релея" if number == 401 else "")
            )
            return result

        relayed = attrs.get(_ATTR_XOR_RELAYED_ADDRESS)
        if not relayed:
            result["error"] = "Аллокация без адреса релея"
            return result

        result["relayed_address"] = _xor_address(relayed, tid)
        result["ok"] = True
        return result

    except asyncio.TimeoutError:
        result["error"] = (
            (
                f"{settings.host}:{settings.port} отвечает на STUN, но не на "
                "запрос релея — похоже, это STUN-сервер, а не TURN"
            )
            if answered
            else (
                f"{settings.host}:{settings.port} не отвечает по UDP. "
                "Проверьте, что контейнер релея запущен и порт открыт; если "
                "сервер стоит за NAT, проверка может не дойти до него изнутри, "
                "хотя у клиентов релей работает"
            )
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("[turn] проверка сорвалась: %s", exc)
        result["error"] = f"Ошибка проверки: {exc}"
        return result
    finally:
        # Аллокацию снимаем ЯВНО. Закрытие сокета серверу ничего не говорит:
        # аллокация висела бы до истечения lifetime, занимая порт из узкого
        # диапазона релея — десяток нажатий кнопки выедали бы его целиком.
        if result["ok"]:
            await _release(
                transport, protocol, username, realm, nonce, password, timeout
            )
        transport.close()


async def _release(
    transport,
    protocol: _StunClient,
    username: str,
    realm: str,
    nonce: bytes,
    password: str,
    timeout: float,
) -> None:
    """Refresh с LIFETIME=0 — освободить аллокацию (RFC 8656 §7)."""
    try:
        tid = os.urandom(12)
        attrs = (
            _attr(_ATTR_LIFETIME, struct.pack(">I", 0))
            + _attr(_ATTR_USERNAME, username.encode("utf-8"))
            + _attr(_ATTR_REALM, realm.encode("utf-8"))
            + _attr(_ATTR_NONCE, nonce)
        )
        message = _pack(_METHOD_REFRESH, _CLASS_REQUEST, tid, attrs)
        transport.sendto(_with_integrity(message, username, realm, password))
        # Ответ ждём коротко и без ретраев: не дождались — аллокация всё равно
        # исчезнет сама через _PROBE_LIFETIME секунд.
        await asyncio.wait_for(protocol.responses.get(), min(timeout, 1.0))
    except Exception:  # noqa: BLE001
        logger.debug("[turn] аллокация проверки не снята явно")
