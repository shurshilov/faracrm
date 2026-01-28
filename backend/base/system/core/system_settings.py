# Copyright 2025 FARA CRM
# Core module - system settings model

from typing import Any
from backend.base.system.dotorm.dotorm.fields import Integer, Char, Text
from backend.base.system.dotorm.dotorm.model import DotModel


class SystemSettings(DotModel):
    """
    Модель для хранения системных настроек.
    
    Хранит настройки в формате ключ-значение.
    Примеры ключей:
        - base_url: базовый URL сервера
        - default_language: язык по умолчанию
        - и др.
    """

    __table__ = "system_settings"
    __auto_crud__ = True
    __auto_crud_prefix__ = "/system"

    id: int = Integer(primary_key=True)
    key: str = Char(max_length=255, description="Уникальный ключ настройки")
    value: str | None = Text(description="Значение настройки")
    description: str | None = Char(
        max_length=500, description="Описание настройки"
    )

    @classmethod
    async def get_value(cls, key: str, default: Any = None) -> Any:
        """
        Получить значение настройки по ключу.
        
        Args:
            key: Ключ настройки
            default: Значение по умолчанию если ключ не найден
            
        Returns:
            Значение настройки или default
        """
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
    async def set_value(cls, key: str, value: str, description: str | None = None):
        """
        Установить значение настройки.
        
        Если ключ существует - обновляет, иначе создаёт новую запись.
        
        Args:
            key: Ключ настройки
            value: Значение
            description: Описание (опционально)
        """
        try:
            records = await cls.search(
                filter=[("key", "=", key)],
                fields=["id"],
                limit=1,
            )
            
            if records:
                # Обновляем существующую
                record = await cls.get(records[0].id)
                record.value = value
                if description:
                    record.description = description
                await record.update()
            else:
                # Создаём новую
                setting = cls(key=key, value=value, description=description)
                await cls.create(setting)
        except Exception:
            # Если таблица ещё не существует, пропускаем
            pass

    @classmethod
    async def get_base_url(cls) -> str:
        """
        Получить базовый URL сервера.
        
        Returns:
            URL или пустая строка если не установлен
        """
        return await cls.get_value("base_url", "")

    @classmethod
    async def ensure_defaults(cls, default_base_url: str = "http://localhost:8000"):
        """
        Создать настройки по умолчанию если они не существуют.
        
        Вызывается при старте сервера.
        
        Args:
            default_base_url: URL по умолчанию
        """
        try:
            # base_url
            existing = await cls.search(
                filter=[("key", "=", "base_url")],
                fields=["id"],
                limit=1,
            )
            if not existing:
                await cls.set_value(
                    key="base_url",
                    value=default_base_url,
                    description="Базовый URL сервера для webhook и внешних ссылок",
                )
        except Exception:
            # Таблица ещё не создана
            pass
