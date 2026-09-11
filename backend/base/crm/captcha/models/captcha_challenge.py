# Copyright 2025 FARA CRM
# Captcha module - задачка капчи (ответ проверяется на сервере)

import secrets
from datetime import datetime, timedelta, timezone

from backend.base.system.dotorm.dotorm.fields import Char, Datetime, Integer
from backend.base.system.dotorm.dotorm.model import DotModel

# Сколько живёт задачка капчи.
CAPTCHA_TTL = timedelta(minutes=10)


class CaptchaChallenge(DotModel):
    """
    Задачка капчи: простой пример «a + b», ответ хранится на сервере.

    Токен = id строки. На проверке строка удаляется (одноразовость): даже
    подобранный ответ нельзя переиспользовать. Наружу CRUD не нужен —
    только публичная ручка «дай задачку» и проверка на стороне потребителя
    (регистрация).
    """

    __table__ = "captcha_challenge"
    __auto_crud__ = False

    id: int = Integer(primary_key=True)
    answer: str = Char(max_length=16, private=True)
    expires_at: datetime = Datetime()
    create_datetime: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    async def new_challenge(cls) -> tuple[str, str]:
        """Создать задачку. Возвращает (token, question), например «3 + 5»."""
        a = secrets.randbelow(9) + 1
        b = secrets.randbelow(9) + 1
        challenge_id = await cls.create(
            payload=cls(
                answer=str(a + b),
                expires_at=datetime.now(timezone.utc) + CAPTCHA_TTL,
            )
        )
        return str(challenge_id), f"{a} + {b}"

    @classmethod
    async def verify(cls, token: str | None, answer: str | None) -> bool:
        """Сверить ответ и погасить задачку (одноразовая)."""
        if not token or not answer:
            return False
        try:
            challenge_id = int(token)
        except (TypeError, ValueError):
            return False

        challenge = await cls.search_one(
            fields=["id", "answer", "expires_at"],
            filter=[("id", "=", challenge_id)],
        )
        if challenge is None:
            return False

        # Гасим в любом случае — задачка одноразовая.
        await challenge.delete()
        if challenge.expires_at < datetime.now(timezone.utc):
            return False
        return secrets.compare_digest(
            (challenge.answer or "").strip(), answer.strip()
        )
