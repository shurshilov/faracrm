# Copyright 2025 FARA CRM
# Cron Locking - PostgreSQL advisory locks for single-instance guarantee
"""
Гарантирует что только один cron worker работает, даже при N uvicorn воркерах.

Использует pg_try_advisory_lock — неблокирующий session-level lock.
При падении процесса PostgreSQL автоматически освобождает lock.
"""

import logging

logger = logging.getLogger(__name__)

# Уникальный ID для cron lock (FARA CRON в hex-like)
CRON_LOCK_ID = 0xFA4AC400


async def try_acquire_cron_lock(pool) -> bool:
    """
    Попытка захватить advisory lock для cron worker.
    Неблокирующий — мгновенно возвращает True/False.

    Args:
        pool: asyncpg.Pool

    Returns:
        True если lock захвачен (мы — единственный cron worker)
        False если lock занят другим процессом
    """
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT pg_try_advisory_lock($1)", CRON_LOCK_ID
        )
        logger.debug("Advisory lock acquire attempt: %s", result)
        return result


async def release_cron_lock(pool) -> None:
    """Освободить advisory lock."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT pg_advisory_unlock($1)", CRON_LOCK_ID)
            logger.debug("Advisory lock released")
    except OSError:
        logger.warning("Failed to release advisory lock", exc_info=True)
