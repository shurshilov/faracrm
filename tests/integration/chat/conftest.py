"""
Общее для тестов чата под настоящими ролями и правилами (test_chat_admins,
test_chat_access): сотрудники с сессиями и привязка глобального env к тестовой
базе.

Сами роли и правила модуль подключает своей autouse-фикстурой _security_init
(post_init после очистки таблиц) — остальные тесты папки идут без них.
"""

import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest_asyncio

from backend.base.crm.security.models.sessions import Session
from backend.base.system.dotorm_databases_postgres.app import (
    DotormDatabasesPostgresService,
)
from tests.integration.security.test_field_access import _role_id


@pytest_asyncio.fixture
async def db_service(db_pool):
    """Отправка сообщения, чат партнёра и record-чат открывают транзакцию
    глобального env — привязываем его Postgres-сервис к тестовой базе (как
    wired_env)."""
    DotormDatabasesPostgresService().set_pool(db_pool)


async def auth_headers(user_id: int) -> dict[str, str]:
    """Сессия пользователя → заголовки запроса (Bearer + session_cookie)."""
    token = secrets.token_urlsafe(32)
    cookie = secrets.token_urlsafe(32)
    await Session.create(
        Session(
            user_id=user_id,
            token=token,
            cookie_token=cookie,
            ttl=3600,
            expired_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            create_user_id=user_id,
            update_user_id=user_id,
            active=True,
        )
    )
    return {
        "Authorization": f"Bearer {token}",
        "Cookie": f"session_cookie={cookie}",
    }


@pytest_asyncio.fixture
async def staff(user_factory):
    """Сотрудники с ролью base_user: id и заголовки их сессий.

    Всё создаётся до первого запроса: дальше тест работает только через
    ручки и SQL.
    """
    base_user = await _role_id("base_user")
    people = {}
    for login in ("alice", "bob", "carol"):
        user = await user_factory(
            name=login.capitalize(),
            login=login,
            role_ids={"selected": [base_user]},
        )
        people[login] = SimpleNamespace(
            id=user.id, headers=await auth_headers(user.id)
        )
    return SimpleNamespace(**people)


async def create_group(client, owner, *user_ids: int) -> int:
    """Группа через ручку: owner — создатель, user_ids — остальные."""
    resp = await client.post(
        "/chats",
        json={
            "name": "Отдел продаж",
            "chat_type": "group",
            "user_ids": list(user_ids),
            "partner_ids": [],
        },
        headers=owner.headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]
