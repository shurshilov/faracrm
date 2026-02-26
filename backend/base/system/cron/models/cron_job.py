# Copyright 2025 FARA CRM
# Cron Job model - with atomic claiming
"""
Модель cron_job с атомарным захватом задач.

Ключевое отличие от старой версии:
- claim_next_jobs() использует SELECT FOR UPDATE SKIP LOCKED
- Никаких race conditions между воркерами
- Одна SQL-транзакция: SELECT + UPDATE → атомарно
"""

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any
import json
import logging

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Float,
    Char,
    Boolean,
    Text,
    Datetime,
    Selection,
)
from backend.base.system.dotorm.dotorm.model import DotModel

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger("cron.jobs")


class CronJob(DotModel):
    """Запланированная задача (cron job)."""

    __table__ = "cron_job"

    id: int = Integer(primary_key=True)

    # Основные поля
    name: str = Char(size=255, required=True, string="Название")
    active: bool = Boolean(default=True, string="Активна")

    # Вариант 1: Код напрямую
    code: str = Text(string="Код (Python)")

    # Вариант 2: Метод модели
    model_name: str = Char(size=255, string="Модель")
    method_name: str | None = Char(size=255, string="Метод")
    args: str = Text(string="Аргументы (JSON)", default="[]")
    kwargs: str = Text(string="Именованные аргументы (JSON)", default="{}")

    interval_number: int = Integer(default=1, string="Интервал")
    interval_type: str = Selection(
        options=[
            ("minutes", "Минуты"),
            ("hours", "Часы"),
            ("days", "Дни"),
            ("weeks", "Недели"),
            ("months", "Месяцы"),
        ],
        default="days",
        string="Тип интервала",
    )

    # Ограничения
    numbercall: int = Integer(default=-1, string="Макс. запусков")
    doall: bool = Boolean(default=False, string="Выполнить пропущенные")

    # Состояние
    nextcall: datetime = Datetime(string="Следующий запуск")
    lastcall: datetime | None = Datetime(string="Последний запуск")
    last_status: str = Selection(
        options=[
            ("pending", "Ожидает"),
            ("running", "Выполняется"),
            ("success", "Успешно"),
            ("error", "Ошибка"),
        ],
        default="pending",
        string="Статус",
    )
    last_error: str | None = Text(string="Последняя ошибка")
    last_duration: float = Float(default=0, string="Длительность (сек)")
    run_count: int = Integer(default=0, string="Кол-во запусков")

    # Настройки
    priority: int = Integer(default=10, string="Приоритет")
    timeout: int = Integer(default=300, string="Таймаут (сек)")

    # ==================== Атомарный захват (Фаза 2) ====================

    @classmethod
    async def claim_next_jobs(cls, pool, limit: int = 5) -> list[dict]:
        """
        Атомарно захватывает следующие задачи для выполнения.

        Использует SELECT FOR UPDATE SKIP LOCKED:
        - Атомарно: SELECT + UPDATE в одной транзакции
        - SKIP LOCKED: пропускает задачи, захваченные другими транзакциями
        - Никаких race conditions

        Returns:
            Список dict с данными задач (уже помеченных как running)
        """
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    WITH claimed AS (
                        SELECT id
                        FROM cron_job
                        WHERE active = true
                          AND (
                              last_status != 'running'
                              OR (lastcall + make_interval(secs => timeout) < $1)
                          )
                          AND (nextcall IS NULL OR nextcall <= $1)
                          AND (numbercall = -1 OR run_count < numbercall)
                        ORDER BY priority ASC
                        LIMIT $2
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE cron_job
                    SET last_status = 'running', lastcall = $1
                    FROM claimed
                    WHERE cron_job.id = claimed.id
                    RETURNING cron_job.*
                    """,
                    now,
                    limit,
                )

        if rows:
            logger.info(
                "Claimed %s jobs: %s",
                len(rows),
                [r["name"] for r in rows],
            )

        return [dict(r) for r in rows]

    @classmethod
    async def complete_job(
        cls,
        pool,
        job_id: int,
        status: str,
        error: str = "",
        duration: float = 0,
        run_count: int = 0,
        next_call: datetime | None = None,
        deactivate: bool = False,
    ) -> None:
        """Обновить статус задачи после выполнения."""
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE cron_job
                SET last_status = $2,
                    last_error = $3,
                    last_duration = $4,
                    run_count = $5,
                    nextcall = $6,
                    active = CASE WHEN $7 THEN false ELSE active END
                WHERE id = $1
                """,
                job_id,
                status,
                error,
                duration,
                run_count,
                next_call,
                deactivate,
            )

    # ==================== Вычисления ====================

    def calculate_next_call(self) -> datetime:
        """Вычисляет следующее время запуска."""
        now = datetime.now(timezone.utc)
        base_time = self.lastcall or now

        deltas = {
            "minutes": timedelta(minutes=self.interval_number),
            "hours": timedelta(hours=self.interval_number),
            "days": timedelta(days=self.interval_number),
            "weeks": timedelta(weeks=self.interval_number),
            "months": timedelta(days=30 * self.interval_number),
        }
        delta = deltas.get(self.interval_type, timedelta(days=1))
        next_call = base_time + delta

        return max(next_call, now)

    # ==================== Выполнение ====================

    async def execute(self, env: "Environment") -> Any:
        """Выполняет задачу."""
        if self.code:
            return await self._execute_code(env)
        if self.model_name and self.method_name:
            return await self._execute_method(env)
        raise ValueError(
            "Either 'code' or 'model_name'+'method_name' must be specified"
        )

    async def _execute_code(self, env: "Environment") -> Any:
        """Выполняет Python код."""
        local_vars = {
            "env": env,
            "datetime": datetime,
            "timedelta": timedelta,
            "json": json,
            "result": {},
        }

        wrapped_code = f"""
async def __cron_task__():
    {self.code.replace(chr(10), chr(10) + '    ')}
    return result
"""
        exec(compile(wrapped_code, f"<cron:{self.name}>", "exec"), local_vars)
        return await local_vars["__cron_task__"]()

    async def _execute_method(self, env: "Environment") -> Any:
        """Выполняет метод модели."""
        model = getattr(env.models, self.model_name, None)
        if model is None:
            raise ValueError(f"Model '{self.model_name}' not found")

        method = getattr(model, self.method_name, None)
        if method is None:
            raise ValueError(
                f"Method '{self.method_name}' not found in '{self.model_name}'"
            )

        args = json.loads(self.args or "[]")
        kwargs = json.loads(self.kwargs or "{}")
        return await method(env, *args, **kwargs)

    # ==================== Утилиты ====================

    @classmethod
    async def get_pending_jobs(cls, env: "Environment") -> list["CronJob"]:
        """Получает список задач (старый API, для совместимости)."""
        now = datetime.now(timezone.utc)
        jobs = await env.models.cron_job.search(
            filter=[
                ("active", "=", True),
                ("last_status", "!=", "running"),
            ],
            order="ASC",
            sort="priority",
        )

        result = []
        for job in jobs:
            if job.nextcall and job.nextcall > now:
                continue
            if job.numbercall != -1 and job.run_count >= job.numbercall:
                continue
            result.append(job)
        return result

    @classmethod
    async def create_or_update(
        cls,
        env: "Environment",
        name: str,
        method_name: str = "",
        code: str = "",
        model_name: str = "cron_job",
        interval_number: int = 1,
        interval_type: str = "days",
        active: bool = True,
        **kwargs,
    ):
        """Создаёт или обновляет задачу по имени."""
        existing = await env.models.cron_job.search(
            filter=[("name", "=", name)],
            limit=1,
        )

        cron_job_new = CronJob(
            name=name,
            code=code,
            model_name=model_name,
            method_name=method_name,
            interval_number=interval_number,
            interval_type=interval_type,
            active=active,
            nextcall=datetime.now(timezone.utc),
            **kwargs,
        )
        if existing:
            job = existing[0]
            await job.update(cron_job_new)
            return job
        else:
            job = await env.models.cron_job.create(cron_job_new)
            return job
