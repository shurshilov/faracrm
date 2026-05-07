# Тесты безопасности

Самый специфичный уровень. Проверяют, что **система не отдаёт данные тому, кому не должна**, и не позволяет обойти проверки прав.

## Когда писать

- Добавил новую роль или Rule — обязательно тест на изоляцию.
- Реализовал bypass-механизм (`SystemSession`, ручной обход ACL) — тест что он работает только в нужном контексте.
- Добавил публичный endpoint — тест на anonymous-доступ и rate-limiting.
- Поправил баг с правами — регрессионный тест, чтобы он не вернулся.

## Когда **не** писать

- В качестве замены integration — у них разные цели. Integration-тест проверяет «что endpoint работает». Security-тест — «что endpoint не работает в обход прав».
- На «тривиальные» проверки (только админ может делать X) если эта логика чисто декларативная — Rule достаточно. Тест нужен на сложных сценариях.

## Структура

```
tests/security/
├── conftest.py                    # многопользовательские фикстуры
├── test_acl_isolation.py          # юзер A не видит данные юзера B
├── test_rules_filtering.py        # Rules корректно фильтруют SELECT
├── test_admin_bypass.py           # is_admin реально обходит проверки
├── test_session_security.py       # сессии: protocol, expiration, hijacking
├── test_anonymous_endpoints.py    # что доступно без авторизации
└── test_input_validation.py       # SQL-инъекции, XSS, path traversal
```

## Главные сценарии

### Изоляция данных между пользователями

```python title="tests/security/test_acl_isolation.py"
@pytest.mark.security
async def test_manager_sees_only_own_leads(env, two_managers):
    """Менеджер видит только своих лидов через Rule user_id={{user_id}}."""
    manager_a, manager_b = two_managers

    # Manager A создаёт лид
    set_access_session(Session(user_id=manager_a))
    lead_a = await env.models.lead.create(payload=Lead(name="Lead A"))

    # Manager B создаёт другой лид
    set_access_session(Session(user_id=manager_b))
    lead_b = await env.models.lead.create(payload=Lead(name="Lead B"))

    # Manager A видит только свой
    set_access_session(Session(user_id=manager_a))
    leads_for_a = await env.models.lead.search()
    lead_ids = [l.id for l in leads_for_a]
    assert lead_a.id in lead_ids
    assert lead_b.id not in lead_ids   # ← главная проверка
```

### Прямой доступ по ID — обход через знание PK

Частая ошибка: фронт фильтрует записи правильно, а на бэке `GET /api/leads/{id}` отдаёт по ID без проверки прав.

```python
async def test_direct_access_by_id_blocked(client, manager_a, manager_b):
    """GET /api/leads/{lead_b_id} от manager_a → 403/404."""
    # manager_b создаёт лид
    headers_b = login_headers(manager_b)
    res = await client.post("/api/leads", json={"name": "Secret"}, headers=headers_b)
    secret_lead_id = res.json()["id"]

    # manager_a пытается прочитать его напрямую
    headers_a = login_headers(manager_a)
    res = await client.get(f"/api/leads/{secret_lead_id}", headers=headers_a)
    assert res.status_code in (403, 404), \
        f"manager_a смог прочитать чужой лид: {res.json()}"
```

### Rules не обходятся через JSON-фильтр

```python
async def test_filter_cannot_bypass_rules(client, manager):
    """Попытка вытянуть чужие лиды через filter: [['user_id', '!=', me]]."""
    headers = login_headers(manager)

    # Кажется, можно искать по обратному условию
    res = await client.get(
        "/api/crud-auto/leads/search",
        params={"filter": '[["user_id", "!=", ' + str(manager.id) + "]]"},
        headers=headers,
    )
    assert res.status_code == 200
    leads = res.json()["data"]

    # Все вернувшиеся записи всё равно должны быть свои —
    # Rule доминирует над пользовательским фильтром
    for lead in leads:
        assert lead["user_id"]["id"] == manager.id
```

### Admin реально админ

```python
async def test_admin_bypasses_rules(env, admin, regular_user):
    """is_admin=true — видит ВСЁ, минуя ACL и Rules."""
    set_access_session(Session(user_id=regular_user))
    user_lead = await env.models.lead.create(payload=Lead(name="User's lead"))

    set_access_session(Session(user_id=admin))
    admin_view = await env.models.lead.search()
    assert any(l.id == user_lead.id for l in admin_view)
```

### Session hijacking невозможен

```python
async def test_expired_session_rejected(client):
    """Использовать токен после expiration — 401."""
    expired_token = create_session_with_expiry(expires_in=-3600)  # уже истёк

    res = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
```

### Input validation

```python
@pytest.mark.parametrize("payload", [
    "'; DROP TABLE users; --",
    "<script>alert(1)</script>",
    "../../../etc/passwd",
    "x" * 10000,                    # огромная строка
    {"$ne": None},                  # NoSQL-injection style
    "%00",                          # null byte
])
async def test_malicious_input_handled(client, manager, payload):
    """Любой malicious-input не падает с 500 и не уходит в БД сырым."""
    headers = login_headers(manager)
    res = await client.post(
        "/api/leads",
        json={"name": payload},
        headers=headers,
    )
    # Допустимо: 400 (validation), 422 (Pydantic), 200 (записалось безопасно)
    # Недопустимо: 500 (упал) или success+вернулся как HTML/JS
    assert res.status_code in (200, 201, 400, 422)
```

## Многопользовательские фикстуры

`tests/security/conftest.py` обычно содержит готовых разных пользователей:

```python
@pytest.fixture
async def two_managers(env, db_pool):
    """Два менеджера с разными ID, чтобы тестировать изоляцию."""
    role = await env.models.role.search(filter=[("code", "=", "manager")])
    a = await env.models.user.create(payload=User(name="A", login="a", role_ids=[role[0].id]))
    b = await env.models.user.create(payload=User(name="B", login="b", role_ids=[role[0].id]))
    return a, b


@pytest.fixture
async def admin_and_user(env):
    admin = await env.models.user.create(payload=User(name="Admin", login="adm", is_admin=True))
    user = await env.models.user.create(payload=User(name="User", login="user"))
    return admin, user
```

## Запуск

```bash
# Все security-тесты
pytest tests/security/ -v -m security

# Только конкретная категория
pytest tests/security/test_acl_isolation.py -v
```

## Что должно быть покрыто

Каждая модель с пользовательскими данными должна иметь хотя бы:

1. **Test isolation**: user A не видит записи user B (если нет соответствующего права).
2. **Test direct-id access**: `GET /model/{other_user_id}` → 403/404.
3. **Test filter bypass**: попытка прочитать через хитрый фильтр блокируется.

Это минимум. Хорошо, если есть ещё:

4. **Test admin bypass**: `is_admin` реально работает.
5. **Test role escalation**: user A не может присвоить себе админскую роль через update.

## CI

Security-тесты должны идти **на каждом PR** — это самый болезненный класс багов в production. Если security-тесты медленные (нагрузочные сценарии перебора), вынеси их в отдельный сюит и гоняй раз в сутки.

## См. также

- [Роли и правила](../security/roles-and-rules.md)
- [Иерархия пользователей](../security/hierarchy.md)
- [Security Module](../modules/security.md)
