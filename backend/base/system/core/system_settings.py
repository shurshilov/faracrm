# Copyright 2025 FARA CRM
# Core module - system settings model with in-memory cache

import time
import logging
from typing import Any

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Text,
    JSONField,
    Boolean,
)
from backend.base.system.dotorm.dotorm.model import DotModel

log = logging.getLogger(__name__)


class _SettingsCache:
    """
    Простой in-memory кеш для системных настроек.

    Хранит пары key → (value, expires_at).
    TTL берётся из поля cache_ttl каждой настройки:
        0  — не кешировать (всегда читать из БД)
       -1  — кешировать навсегда (до перезагрузки)
       >0  — кешировать N секунд
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> tuple[bool, Any]:
        """Вернуть (found, value). found=False если нет или протухло."""
        entry = self._store.get(key)
        if entry is None:
            return False, None

        value, expires_at = entry
        # expires_at == 0 означает «навсегда»
        if expires_at != 0 and time.monotonic() > expires_at:
            del self._store[key]
            return False, None

        return True, value

    def put(self, key: str, value: Any, ttl: int) -> None:
        """Положить в кеш. ttl: 0=не кешировать, -1=навсегда, >0=секунды."""
        if ttl == 0:
            self._store.pop(key, None)
            return
        expires_at = 0 if ttl < 0 else time.monotonic() + ttl
        self._store[key] = (value, expires_at)

    def invalidate(self, key: str) -> None:
        """Удалить ключ из кеша."""
        self._store.pop(key, None)


# Один экземпляр на процесс
_cache = _SettingsCache()


class SystemSettings(DotModel):
    """
    Системные настройки (key-value, JSON) с кешированием.

    Хранит бизнес-конфигурацию, которую можно менять на лету
    без перезапуска сервера. Инфраструктурные параметры
    (DATABASE_URL, SECRET_KEY и т.д.) остаются в .env.

    Поле cache_ttl управляет кешированием:
        0  — не кешировать (каждый раз из БД)
       -1  — кешировать навсегда (до перезагрузки сервера)
       >0  — кешировать на N секунд

    Примеры:
        key="attachments.filestore_path"  value={"value":"/data/filestore"}  cache_ttl=-1
        key="mail.smtp_host"              value={"value":"smtp.gmail.com"}   cache_ttl=600
        key="auth.session_ttl"            value={"value":86400}              cache_ttl=0
    """

    __table__ = "system_settings"

    id: int = Integer(primary_key=True)
    key: str = Char(
        max_length=255,
        required=True,
        unique=True,
        string="Key",
        description="Уникальный ключ настройки (формат: module.param_name)",
    )
    value: dict | list | None = JSONField(
        default=None,
        string="Value",
        description="Значение настройки (JSON: строка, число, объект, массив, bool)",
    )
    description: str | None = Text(
        default=None,
        string="Description",
        description="Описание настройки",
    )
    module: str = Char(
        max_length=128,
        default="general",
        string="Module",
        description="Модуль к которому относится настройка",
    )
    is_system: bool = Boolean(
        default=False,
        string="System",
        description="Системная настройка (нельзя удалить через UI)",
    )
    cache_ttl: int = Integer(
        default=0,
        string="Cache TTL",
        description="Кеш: 0 — не кешировать, -1 — навсегда, >0 — секунды",
    )

    # ==================== API ====================

    @classmethod
    async def get_value(cls, key: str, default=None):
        """
        Получить значение по ключу.
        Сначала проверяет кеш, при промахе — БД.
        """
        # 1. кеш
        found, cached = _cache.get(key)
        if found:
            return cached

        # 2. БД
        try:
            records = await cls.search(
                filter=[("key", "=", key)],
                fields=["value", "cache_ttl"],
                limit=1,
            )
            if records:
                raw = records[0].value
                ttl = getattr(records[0], "cache_ttl", 0) or 0

                # Извлекаем значение
                if raw and isinstance(raw, dict):
                    result = raw.get("value", raw)
                elif isinstance(raw, list):
                    result = raw
                else:
                    result = raw

                # Кладём в кеш
                _cache.put(key, result, ttl)
                return result

            return default
        except Exception:
            return default

    @classmethod
    async def set_value(
        cls,
        key: str,
        value: dict,
        description: str | None = None,
        module: str = "general",
        cache_ttl: int = 0,
    ):
        """
        Установить значение (upsert).
        Инвалидирует кеш при записи.
        """
        _cache.invalidate(key)

        records = await cls.search(
            filter=[("key", "=", key)],
            fields=["id"],
            limit=1,
        )

        if records:
            record = records[0]
            settings = cls(value=value, description=description)
            if cache_ttl is not None:
                settings.cache_ttl = cache_ttl
            await record.update(settings)
        else:
            setting = cls(
                key=key,
                value=value,
                description=description,
                module=module,
                cache_ttl=cache_ttl,
            )
            await cls.create(setting)

    @classmethod
    async def get_by_module(cls, module: str):
        """Получить все настройки модуля."""
        return await cls.search(
            filter=[("module", "=", module)],
            fields=[
                "id",
                "key",
                "value",
                "description",
                "module",
                "is_system",
                "cache_ttl",
            ],
        )

    @classmethod
    async def ensure_defaults(cls, defaults: list[dict]):
        """
        Создать настройки по умолчанию если они не существуют.
        Вызывается при старте сервера.

        Args:
            defaults: [{"key": "...", "value": ..., "description": "...",
                        "module": "...", "cache_ttl": 0}]
        """
        try:
            for item in defaults:
                existing = await cls.search(
                    filter=[("key", "=", item["key"])],
                    fields=["id"],
                    limit=1,
                )
                if not existing:
                    setting = cls(
                        key=item["key"],
                        value=item.get("value"),
                        description=item.get("description", ""),
                        module=item.get("module", "general"),
                        is_system=item.get("is_system", False),
                        cache_ttl=item.get("cache_ttl", 0),
                    )
                    await cls.create(setting)
        except Exception:
            pass

    # ==================== Обратная совместимость ====================

    @classmethod
    async def get_base_url(cls):
        """Получить базовый URL сервера."""
        return await cls.get_value("base_url", "")
