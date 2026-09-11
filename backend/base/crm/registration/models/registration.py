# Copyright 2025 FARA CRM
# Registration module - заявка на регистрацию (до подтверждения кода)

import secrets
from datetime import datetime, timedelta, timezone
from typing import Self

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Datetime,
    Integer,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.users.models.users import User
from backend.base.crm.captcha.models.captcha_challenge import CaptchaChallenge
from backend.base.crm.registration.strategies import get_channel

# Сколько живёт код подтверждения.
CODE_TTL = timedelta(minutes=15)

# Настройка с параметрами создаваемого пользователя:
#   {"role_code": "...", "workspace_name": "...", "home_page": "/..."}.
# Сам модуль регистрации её НЕ сидит — значение задаёт модуль, ради которого
# регистрация включена (см. marketplace/app.py). Без настройки пользователь
# создаётся без ролей: войти сможет, а данных не увидит (default-deny).
NEW_USER_SETTING = "registration.new_user"


class Registration(DotModel):
    """
    Заявка на регистрацию: живёт до подтверждения кода.

    Пароль хранится сразу хешем (как у User) — при подтверждении hash+salt
    просто переносятся в новую запись пользователя.
    """

    __table__ = "registration"
    # Только через публичные ручки регистрации, generic CRUD не нужен.
    __auto_crud__ = False

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=256)
    login: str = Char(max_length=256, index=True)
    channel: str = Char(max_length=32, description="Канал доставки кода")
    password_hash: str = Char(max_length=256, private=True)
    password_salt: str = Char(max_length=256, private=True)
    code: str = Char(max_length=16, private=True)
    expires_at: datetime = Datetime()
    confirmed: bool = Boolean(default=False)
    create_datetime: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    async def start(
        cls,
        *,
        name: str,
        login: str,
        password: str,
        channel: str,
        captcha_token: str | None = None,
        captcha_answer: str | None = None,
    ) -> Self:
        """Создать заявку и отправить код выбранным каналом."""
        login = login.strip().lower()
        sender = get_channel(channel)

        existing = await env.models.user.search(
            filter=[("login", "=", login)], fields=["id"], limit=1
        )
        if existing:
            raise FaraException(
                {
                    "content": "REGISTRATION_LOGIN_EXISTS",
                    "detail": "Пользователь с таким логином уже существует",
                }
            )

        policy = await User.get_password_policy(env)
        errors = User.validate_password(password, policy)
        if errors:
            raise FaraException(
                {
                    "content": "REGISTRATION_PASSWORD_POLICY",
                    "detail": ", ".join(errors),
                }
            )

        # Капчу проверяем последней из валидаций и гасим её здесь: провал
        # других проверок (почта, пароль) капчу не тратит — можно повторить
        # с той же задачкой; неверная капча — с новой (фронт перезапросит).
        if not await CaptchaChallenge.verify(captcha_token, captcha_answer):
            raise FaraException(
                {
                    "content": "REGISTRATION_CAPTCHA_INVALID",
                    "detail": "Неверная капча",
                }
            )

        # Одна ожидающая заявка на логин: прежние коды перестают действовать.
        pending = await cls.search(
            filter=[("login", "=", login), ("confirmed", "=", False)],
            fields=["id"],
        )
        for old in pending:
            await old.delete()

        salt = secrets.token_hex(64)
        registration = cls(
            name=name.strip(),
            login=login,
            channel=channel,
            password_hash=User().generate_password_hash(password, salt),
            password_salt=salt,
            code=f"{secrets.randbelow(10**6):06d}",
            expires_at=datetime.now(timezone.utc) + CODE_TTL,
        )
        await cls.create(payload=registration)
        await sender.send_code(registration)
        return registration

    @classmethod
    async def confirm(cls, *, login: str, code: str) -> int:
        """Сверить код, создать пользователя. Возвращает id пользователя."""
        login = login.strip().lower()
        code = "".join(ch for ch in code if ch.isdigit())

        rows = await cls.search(
            filter=[("login", "=", login), ("confirmed", "=", False)],
            fields=[
                "id",
                "name",
                "login",
                "code",
                "password_hash",
                "password_salt",
                "expires_at",
            ],
            sort="id",
            order="desc",
            limit=1,
        )
        registration = rows[0] if rows else None
        if registration is None or not secrets.compare_digest(
            registration.code or "", code
        ):
            raise FaraException(
                {
                    "content": "REGISTRATION_CODE_INVALID",
                    "detail": "Неверный код подтверждения",
                }
            )
        if registration.expires_at < datetime.now(timezone.utc):
            raise FaraException(
                {
                    "content": "REGISTRATION_CODE_EXPIRED",
                    "detail": "Срок действия кода истёк",
                }
            )

        user_id = await registration._create_user()
        await registration.update(cls(confirmed=True))
        return user_id

    async def _create_user(self) -> int:
        defaults = (
            await env.models.system_settings.get_value(NEW_USER_SETTING) or {}
        )
        payload = User(
            name=self.name,
            login=self.login,
            password_hash=self.password_hash,
            password_salt=self.password_salt,
            home_page=defaults.get("home_page") or "/",
        )
        workspace_name = defaults.get("workspace_name")
        if workspace_name:
            workspace = await env.models.workspace.search(
                filter=[("name", "=", workspace_name)],
                fields=["id"],
                limit=1,
            )
            if workspace:
                payload.workspace_id = workspace[0]
        user_id = await env.models.user.create(payload=payload)

        role_code = defaults.get("role_code")
        if role_code:
            role = await env.models.role.search(
                filter=[("code", "=", role_code)], fields=["id"], limit=1
            )
            if role:
                user = await env.models.user.get(user_id)
                # m2m пишется только через update (как в users/app.py).
                await user.update(User(role_ids={"selected": [role[0].id]}))
        return user_id
