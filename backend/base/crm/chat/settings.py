# Copyright 2025 FARA CRM
# Chat module - settings
"""
Настройки модуля chat.

Переменные окружения:
    CHAT__PUBSUB_BACKEND: str = "pg"    - backend pub/sub: "pg" или "redis"
    CHAT__REDIS_URL: str = "redis://localhost:6379/0" - URL Redis (если backend=redis)

Примеры .env:
    # PostgreSQL (по умолчанию, zero config):
    CHAT__PUBSUB_BACKEND=pg

    # Redis:
    CHAT__PUBSUB_BACKEND=redis
    CHAT__REDIS_URL=redis://localhost:6379/0

    # Redis с паролем:
    CHAT__REDIS_URL=redis://:mypassword@redis-host:6379/0

    # Redis с SSL:
    CHAT__REDIS_URL=rediss://redis-host:6380/0
"""

from typing import ClassVar, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class TurnSettings(BaseSettings):
    """
    Настройки STUN/TURN (env-префикс TURN__).

    Один источник ICE на ВСЕ звонки: и на внутренние WebRTC между
    сотрудниками, и на звонилку в браузере к АТС. Раньше каждый сценарий
    носил свой список: внутренние — захардкоженный Google STUN, SIP —
    строку в коннекторе. Отсюда «у одних работает, у других нет».

    Креды выдаются КОРОТКОЖИВУЩИЕ по схеме TURN REST API (RFC 7635):
    username = "<unixtime истечения>:<user_id>", password = base64 от
    HMAC-SHA1(secret, username). Сервер релея знает только secret —
    пользователей заводить и синхронизировать не нужно.

    ЧТО ГДЕ НАСТРАИВАЕТСЯ. Значения ниже — только дефолты: почти все они
    переопределяются из интерфейса (системные настройки, ключи turn.*), и
    правка применяется со следующего звонка, без перезапуска. Исключение —
    секрет: он общий с сервером релея, тот читает его при старте, поэтому из
    интерфейса его менять нельзя (см. resolve_settings в turn.py).

    Пример .env (coturn поднят рядом, см. docker-compose.yml):
        TURN__ENABLED=true
        TURN__HOST=crm.example.com
    """

    # Префикс обязателен: поля называются host/port/secret, и без него
    # вложенная модель подхватила бы чужие переменные окружения — PORT в
    # докере есть почти всегда.
    model_config = SettingsConfigDict(env_prefix="turn__", extra="ignore")

    # Включено по умолчанию: релей едет в том же docker-compose и стартует
    # вместе с остальным, а звонки без него не соединяются у всех, кто сидит
    # за симметричным NAT или в офисе с закрытым UDP. Выключать имеет смысл
    # там, где своего релея действительно нет.
    enabled: bool = True

    # Публичный адрес релея (домен или IP). Именно ПУБЛИЧНЫЙ: адрес попадает
    # в браузер клиента, имя докер-сервиса тут не подойдёт. Пусто — берём
    # домен из site_url: релей едет на той же машине, что и CRM, так что
    # отдельно его прописывать обычно не нужно.
    host: str = ""

    # 3478 — UDP+TCP. 5349 — TLS, но включать его имеет смысл только когда у
    # релея есть сертификат: анонсировать turns: в пустоту — это лишние
    # секунды перебора кандидатов у каждого звонка. Поэтому по умолчанию 0.
    port: int = 3478
    tls_port: int = 0

    # Общий секрет с сервером релея. Обычно пустой: секрет генерируется при
    # первом старте и лежит в файле общего тома (secret_file) — так его не
    # нужно ни придумывать, ни держать в двух местах. Заданный здесь имеет
    # приоритет: это путь для тех, кто носит секреты своим менеджером.
    secret: str = ""

    # Файл с секретом, общий с контейнером релея. Пустой путь = не искать
    # (так работают dev-запуск и тесты — они не должны зависеть от того, что
    # лежит в файловой системе машины).
    secret_file: str = ""

    # Сколько живут выданные креды. Час с запасом покрывает длинный разговор:
    # проверка идёт в момент выдачи аллокации, а не всю сессию.
    ttl: int = 3600

    # Гонять ВЕСЬ трафик через релей (iceTransportPolicy=relay). Прячет
    # реальные IP собеседников друг от друга, но грузит сервер — выключено.
    force_relay: bool = False

    # Запасные STUN: и когда своего релея нет, и как страховка, если он упал.
    # Пустой список = никаких внешних зависимостей (закрытый контур).
    fallback_stun: list[str] = [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302",
    ]

    # Ключи, которые админ меняет из интерфейса. Секрет и путь к нему сюда НЕ
    # входят: секрет обязан совпадать с тем, что получил контейнер релея, и
    # правка «на лету» в БД молча сломала бы все звонки через релей.
    UI_KEYS: ClassVar[tuple[str, ...]] = (
        "enabled",
        "host",
        "port",
        "tls_port",
        "ttl",
        "force_relay",
        "fallback_stun",
    )


class ChatSettings(BaseSettings):
    """Настройки Chat модуля."""

    # Pub/Sub backend: "pg" (PostgreSQL LISTEN/NOTIFY) или "redis"
    pubsub_backend: Literal["pg", "redis"] = "pg"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_channel: str = "ws_events"

    # PostgreSQL
    pg_channel: str = "ws_events"
    pg_max_payload: int = 7900
