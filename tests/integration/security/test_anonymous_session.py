"""
Анонимная сессия публичных ручек: прав нет вообще.

Раньше AnonymousSession несла белый список таблиц на чтение (per-роутер).
Список проверялся только на корневой модели запроса — вложенные связи
грузились без ACL связанной таблицы, а грант означал всю таблицу без
правил. Теперь под анонимной сессией запрещено всё; что публичной ручке
нужно, она читает сама через .sudo() по точному фильтру и явным полям.

Run: pytest tests/integration/security/test_anonymous_session.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration

from backend.base.crm.company.models.company import Company
from backend.base.crm.partners.models.partners import Partner
from backend.base.crm.security.models.sessions import (
    AnonymousSession,
    SystemSession,
)
from backend.base.crm.users.models.users import (
    ANONYMOUS_USER_ID,
    SYSTEM_USER_ID,
)
from backend.base.system.dotorm.dotorm.access import (
    AccessDenied,
    get_access_session,
    set_access_session,
)


class as_anonymous:
    """Временно подменить сессию доступа анонимной (conftest ставит
    системную)."""

    def __enter__(self):
        self._prev = get_access_session()
        set_access_session(AnonymousSession())

    def __exit__(self, *exc):
        set_access_session(self._prev)


class TestAnonymousOrm:
    async def test_read_denied(self):
        with as_anonymous():
            with pytest.raises(AccessDenied):
                await Company.search(fields=["id"])

    async def test_write_denied(self):
        with as_anonymous():
            with pytest.raises(AccessDenied):
                await Company.create(Company(name="Anon Co"))

    async def test_sudo_reads(self):
        """Публичная ручка читает нужное сама — под sudo, явными полями."""
        company_id = await Company.create(Company(name="Sudo Co"))
        with as_anonymous():
            found = await Company.sudo().search_one(
                fields=["id", "name"], filter=[("id", "=", company_id)]
            )
        assert found is not None
        assert found.name == "Sudo Co"


class TestSudoKeepsActor:
    async def test_anonymous_actor_recorded(self):
        """Под sudo права системные, а автор записи — вызывающий: у
        публичной ручки это Anonymous (id=4), а не System."""
        with as_anonymous():
            partner_id = await Partner.sudo().create(
                Partner(name="Anon Partner")
            )
        partner = await Partner.search_one(
            fields=["id", "create_user_id"],
            fields_nested={"create_user_id": {"fields": ["id"]}},
            filter=[("id", "=", partner_id)],
        )
        assert partner is not None
        assert partner.create_user_id.id == ANONYMOUS_USER_ID

    def test_lang_is_english(self):
        assert AnonymousSession().get_lang() == "en"
        assert SystemSession(user_id=SYSTEM_USER_ID).get_lang() == "en"


class TestPublicRoutes:
    """Запросы без входа: ручки работают под анонимной сессией через sudo."""

    async def test_version(self, client):
        response = await client.get("/version/")
        assert response.status_code == 200

    async def test_public_config(self, client):
        # post_init сеет компанию по умолчанию (sequence=10); ручка берёт
        # первую по sequence — наша должна идти раньше неё.
        await Company.create(
            Company(name="Branded", login_title="Hello", sequence=0)
        )
        response = await client.get("/public/config/")
        assert response.status_code == 200
        assert response.json()["branding"]["login_title"] == "Hello"
