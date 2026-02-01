# Copyright 2025 FARA CRM
# Cron Job model - scheduled tasks definition
"""
Модель cron_job - запланированные задачи.

Архитектура:
- Задачи хранятся в БД
- Можно указать код напрямую (поле code) или метод модели (model_name + method_name)
- Код выполняется через exec() с доступом к env

Пример создания задачи с кодом:

    await CronJob.create_or_update(
        env=env,
        name="Тестовая задача",
        code='''
user = await env.models.user.create(...)
result = {"created_user_id": user.id}
''',
        interval_number=1,
        interval_type="days",
        active=False,
    )

Пример с методом модели:

    await CronJob.create_or_update(
        env=env,
        name="Очистка сообщений",
        model_name="chat_message",
        method_name="_cron_cleanup_old",
        kwargs='{"days": 30}',
    )
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

logger = logging.getLogger("cron")


class CronJob(DotModel):
    """
    Запланированная задача (cron job).
    """

    __table__ = "cron_job"

    id: int = Integer(primary_key=True)

    # Основные поля
    name: str = Char(
        size=255,
        required=True,
        string="Название",
    )
    active: bool = Boolean(
        default=True,
        string="Активна",
    )

    # Вариант 1: Код напрямую
    code: str = Text(
        string="Код (Python)",
    )

    # Вариант 2: Метод модели
    # model_name - имя модели в env.models (например "user", "chat_message")
    model_name: str = Char(
        size=255,
        string="Модель",
    )
    method_name: str = Char(
        size=255,
        string="Метод",
    )
    args: str = Text(
        string="Аргументы (JSON)",
        default="[]",
    )
    kwargs: str = Text(
        string="Именованные аргументы (JSON)",
        default="{}",
    )

    interval_number: int = Integer(
        default=1,
        string="Интервал",
    )
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
    numbercall: int = Integer(
        default=-1,
        string="Макс. запусков",
    )
    doall: bool = Boolean(
        default=False,
        string="Выполнить пропущенные",
    )

    # Состояние
    nextcall: datetime = Datetime(
        string="Следующий запуск",
    )
    lastcall: datetime = Datetime(
        string="Последний запуск",
    )
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
    last_error: str = Text(
        string="Последняя ошибка",
    )
    last_duration: float = Float(
        string="Длительность (сек)",
    )
    run_count: int = Integer(
        default=0,
        string="Кол-во запусков",
    )

    # Настройки
    priority: int = Integer(
        default=10,
        string="Приоритет",
    )
    timeout: int = Integer(
        default=300,
        string="Таймаут (сек)",
    )

    # ==================== Служебные методы ====================

    def calculate_next_call(self) -> datetime:
        """
        Вычисляет следующее время запуска на основе интервала.
        """
        now = datetime.now(timezone.utc)
        base_time = self.lastcall or now

        if self.interval_type == "minutes":
            delta = timedelta(minutes=self.interval_number)
        elif self.interval_type == "hours":
            delta = timedelta(hours=self.interval_number)
        elif self.interval_type == "days":
            delta = timedelta(days=self.interval_number)
        elif self.interval_type == "weeks":
            delta = timedelta(weeks=self.interval_number)
        elif self.interval_type == "months":
            # Приблизительно 30 дней
            delta = timedelta(days=30 * self.interval_number)
        else:
            delta = timedelta(days=1)

        next_call = base_time + delta

        # Если следующий запуск в прошлом, ставим сейчас
        if next_call < now:
            next_call = now

        return next_call

    async def execute(self, env: "Environment") -> Any:
        """
        Выполняет задачу.

        Если указан code - выполняет его через exec().
        Иначе вызывает метод модели.
        """
        # Вариант 1: Код напрямую
        if self.code:
            return await self._execute_code(env)

        # Вариант 2: Метод модели
        if self.model_name and self.method_name:
            return await self._execute_method(env)

        raise ValueError(
            "Either 'code' or 'model_name'+'method_name' must be specified"
        )

    async def _execute_code(self, env: "Environment") -> Any:
        """
        Выполняет Python код.

        Доступные переменные в коде:
        - env: Environment с доступом к моделям
        - datetime, timedelta: для работы с датами
        - json: для работы с JSON
        - result: словарь для возврата результата
        """
        # Подготавливаем контекст выполнения
        local_vars = {
            "env": env,
            "datetime": datetime,
            "timedelta": timedelta,
            "json": json,
            "result": {},
        }

        # Оборачиваем код в async функцию для поддержки await
        wrapped_code = f"""
async def __cron_task__():
    {self.code.replace(chr(10), chr(10) + '    ')}
    return result
"""

        # Компилируем и выполняем
        exec(compile(wrapped_code, f"<cron:{self.name}>", "exec"), local_vars)

        # Вызываем async функцию
        return await local_vars["__cron_task__"]()

    async def _execute_method(self, env: "Environment") -> Any:
        """
        Выполняет метод модели.
        """
        model = getattr(env.models, self.model_name, None)

        if model is None:
            raise ValueError(
                f"Model '{self.model_name}' not found in env.models"
            )

        method = getattr(model, self.method_name, None)

        if method is None:
            raise ValueError(
                f"Method '{self.method_name}' not found in model '{self.model_name}'"
            )

        # Парсим аргументы
        args = json.loads(self.args or "[]")
        kwargs = json.loads(self.kwargs or "{}")

        # Вызываем метод (первый аргумент - env)
        return await method(env, *args, **kwargs)

    @classmethod
    async def get_pending_jobs(cls, env: "Environment") -> list["CronJob"]:
        """
        Получает список задач, которые нужно выполнить.
        """
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
        """
        Создаёт или обновляет задачу по имени.
        Используется в post_init для идемпотентного создания задач.
        """
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
