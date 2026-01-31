# Copyright 2025 FARA CRM
# Core module - system settings model

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Text,
    JSONField,
    Boolean,
)
from backend.base.system.dotorm.dotorm.model import DotModel


class SystemSettings(DotModel):
    """
    Системные настройки (key-value, JSON).

    Хранит бизнес-конфигурацию, которую можно менять на лету
    без перезапуска сервера. Инфраструктурные параметры
    (DATABASE_URL, SECRET_KEY и т.д.) остаются в .env.

    Примеры:
        key="attachments.filestore_path"  value="/data/filestore"     module="attachments"
        key="mail.smtp_host"              value="smtp.gmail.com"      module="mail"
        key="auth.session_timeout"        value=3600                  module="auth"
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

    # ==================== API ====================

    @classmethod
    async def get_value(cls, key: str, default=None):
        """Получить значение по ключу."""
        try:
            records = await cls.search(
                filter=[("key", "=", key)],
                fields=["value"],
                limit=1,
            )
            if records:
                return records[0].value
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
    ):
        """
        Установить значение (upsert).
        Если ключ есть — обновляет, иначе создаёт.
        """
        records = await cls.search(
            filter=[("key", "=", key)],
            fields=["id"],
            limit=1,
        )

        if records:
            record = records[0]
            record.value = value
            record.description = description
            await record.update()
        else:
            setting = cls(
                key=key,
                value=value,
                description=description,
                module=module,
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
            ],
        )

    @classmethod
    async def ensure_defaults(cls, defaults: list[dict]):
        """
        Создать настройки по умолчанию если они не существуют.
        Вызывается при старте сервера.

        Args:
            defaults: [{"key": "...", "value": ..., "description": "...", "module": "..."}]
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
                    )
                    await cls.create(setting)
        except Exception:
            pass

    # ==================== Обратная совместимость ====================

    @classmethod
    async def get_base_url(cls):
        """Получить базовый URL сервера."""
        return await cls.get_value("base_url", "")
