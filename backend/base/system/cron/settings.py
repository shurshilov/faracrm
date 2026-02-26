# Copyright 2025 FARA CRM
# Cron settings
"""
Настройки модуля cron.

Переменные окружения:
    CRON__ENABLED: bool = True - включить/выключить cron worker
    CRON__CHECK_INTERVAL: int = 60 - интервал проверки задач (секунды)
    CRON__MAX_THREADS: int = 2 - максимум параллельных задач
    CRON__RUN_ON_STARTUP: bool = True - (deprecated, ignored)

Пример .env:
    CRON__ENABLED=true
    CRON__CHECK_INTERVAL=60
    CRON__MAX_THREADS=2
"""

from pydantic_settings import BaseSettings


class CronSettings(BaseSettings):
    """Настройки Cron модуля."""

    # Включить/выключить cron worker
    enabled: bool = True

    # Интервал проверки задач (секунды)
    check_interval: int = 60

    # Максимум параллельных задач
    max_threads: int = 2

    # Deprecated: раньше управлял запуском в lifespan, теперь игнорируется
    run_on_startup: bool = True
