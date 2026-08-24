"""
Матрица удаления guard-куки (cookie_token) при 401.

Кука одна на весь браузер и общая для всех вкладок. Обработчик 401 раньше
звал delete_cookie() на ЛЮБОЙ auth-ошибке, поэтому запрос из протухшей
вкладки сносил куку живой сессии в остальных — те на следующем же запросе
получали SessionErrorFormat -> 401 -> логаут. Каскад.

Теперь удаление разрешено только когда доказано, что кука принадлежит именно
той сессии, которая умерла (флаг AuthFailed.clear_cookie ставится в месте
выброса). Проверяемая матрица:

    Bearer не найден / отозван (кука ещё не сверена)  -> куку НЕ удаляем
    кука не совпала с сессией                         -> НЕ удаляем
    нет заголовка или нет куки (SessionErrorFormat)   -> НЕ удаляем
    кука совпала + сессия истекла или отозвана        -> УДАЛЯЕМ
    by_cookie: нашли по куке, истекла/отозвана        -> УДАЛЯЕМ
    by_cookie: по куке ничего не нашли                -> НЕ удаляем

Остаточное ограничение (тестом не покрывается, покрыть нечем): delete_cookie
удаляет куку по ИМЕНИ, а не по значению. Если логин в другой вкладке случился
между отправкой запроса и ответом, свежая кука всё равно будет снесена. Окно
сузилось с «любой 401» до «истёкшая сессия со сверенной кукой ровно в момент
логина», но не до нуля.

Run: pytest tests/integration/security/test_auth_cookie_matrix.py -v
"""

import ast
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.auth_token.session_cache import CachedSession
from backend.base.crm.security.exceptions import AuthException
from backend.base.crm.security.models import sessions as sessions_module
from backend.base.crm.security.models.sessions import Session
from tests.conftest import auto

# Любой приватный роут под verify_access годится: 401 отдаётся до
# бизнес-логики.
SEARCH_URL = auto("/users/search")
SEARCH_BODY = {"fields": ["id", "name"]}


# ============================================================================
# Хелперы
# ============================================================================


async def _make_db_session(
    user_id: int, *, expired: bool = False
) -> tuple[int, str, str]:
    """Создаёт запись сессии, возвращает (id, token, cookie_token).

    Истечение задаётся датой в прошлом, а не ожиданием: TTL сессии — 7 дней.
    """
    token = secrets.token_urlsafe(64)
    cookie_token = secrets.token_urlsafe(64)
    now = datetime.now(timezone.utc)
    shift = timedelta(hours=-1 if expired else 1)
    session_id = await Session.create(
        Session(
            user_id=user_id,
            token=token,
            cookie_token=cookie_token,
            ttl=3600,
            expired_datetime=now + shift,
            create_user_id=user_id,
            update_user_id=user_id,
            active=True,
        )
    )
    return session_id, token, cookie_token


def _check_by_token(cached: bool):
    """Проверка Bearer+кука: кэшируемая или прямая — по режиму."""
    return Session.session_check_cached if cached else Session.session_check


def _check_by_cookie(cached: bool):
    """Проверка только по куке (бинарный контент)."""
    return (
        Session.session_check_by_cookie_cached
        if cached
        else Session.session_check_by_cookie
    )


def _guard_cookie_headers(response, cookie_name: str) -> list[str]:
    """Set-Cookie, относящиеся к guard-куке. Пустой список = не тронули."""
    return [
        header
        for header in response.headers.get_list("set-cookie")
        if header.split("=", 1)[0].strip() == cookie_name
    ]


def _is_deleting(header: str) -> bool:
    """delete_cookie() гасит куку через Max-Age=0 и expires в 1970."""
    low = header.lower()
    return "max-age=0" in low or "expires=thu, 01 jan 1970" in low


@pytest_asyncio.fixture(params=[False, True], ids=["db", "cache"])
async def cache_mode(request, _security_init):
    """Гоняет каждый тест по обеим веткам проверки: БД и SessionCache.

    Ветки — параллельные реализации одной логики, и решение про clear_cookie в
    них дублируется. Разъезд веток = дыра ровно в том месте, которое чинили.

    _security_init запрошен явно: он гоняет post_init, который переставляет
    session_cache_enabled, — фикстура обязана отработать ПОСЛЕ него.
    Кэш чистим с двух сторон: он переживает TRUNCATE, а id сессий после
    RESTART IDENTITY начинаются заново и схлопнулись бы со старыми записями.
    """
    previous = AuthTokenApp.session_cache_enabled
    AuthTokenApp.session_cache_enabled = request.param
    await AuthTokenApp.session_cache.clear()
    yield request.param
    await AuthTokenApp.session_cache.clear()
    AuthTokenApp.session_cache_enabled = previous


# ============================================================================
# Уровень модели: кто как ставит clear_cookie
# ============================================================================


class TestSessionCheckClearCookie:
    """session_check / session_check_cached — Bearer + кука."""

    async def test_live_session_with_matching_cookie_passes(
        self, user_factory, cache_mode
    ):
        """Опорная точка: живая сессия со своей кукой проходит проверку."""

        user = await user_factory(login="live_ok")
        session_id, token, cookie_token = await _make_db_session(user.id)

        session = await _check_by_token(cache_mode)(
            token, cookie_token=cookie_token
        )

        assert session.user_id.id == user.id
        # Сверяем id, а не active: в cached-ветке active захардкожен в True,
        # и такой assert не смог бы упасть.
        assert session.id == session_id

    async def test_unknown_bearer_keeps_cookie(self, user_factory, cache_mode):
        """Bearer неизвестен — куку сверить не с чем, значит не трогаем.

        Мусорный Bearer прилетает из вкладки, чей localStorage отстал; кука при
        этом может принадлежать живой сессии.
        """

        user = await user_factory(login="unknown_bearer")
        _, _, cookie_token = await _make_db_session(user.id)

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await _check_by_token(cache_mode)(
                "definitely-not-a-token", cookie_token=cookie_token
            )

        assert exc_info.value.clear_cookie is False

    async def test_foreign_cookie_keeps_cookie(self, user_factory, cache_mode):
        """Кука от ДРУГОЙ (живой) сессии — удалять её нельзя ни при каких.

        Ровно этот случай ломал соседние вкладки: браузер шлёт актуальную куку
        вместе со старым Bearer.
        """

        user = await user_factory(login="foreign_cookie")
        _, stale_token, _ = await _make_db_session(user.id)
        _, _, live_cookie = await _make_db_session(user.id)

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await _check_by_token(cache_mode)(
                stale_token, cookie_token=live_cookie
            )

        assert exc_info.value.clear_cookie is False

    async def test_missing_cookie_keeps_cookie(self, user_factory, cache_mode):
        """Куки в запросе нет — удалять нечего и незачем (Token Binding)."""

        user = await user_factory(login="no_cookie")
        _, token, _ = await _make_db_session(user.id)

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await _check_by_token(cache_mode)(token, cookie_token=None)

        assert exc_info.value.clear_cookie is False

    async def test_expired_session_with_own_cookie_clears_cookie(
        self, user_factory, cache_mode
    ):
        """Кука сверена и сессия умерла — только тут удаление законно.

        Сверка куки стоит ВЫШЕ проверки срока именно ради этого: раз дошли до
        строки про истечение, кука точно принадлежит этой сессии.
        """

        user = await user_factory(login="expired_own")
        _, token, cookie_token = await _make_db_session(user.id, expired=True)

        with pytest.raises(AuthException.SessionExpired) as exc_info:
            await _check_by_token(cache_mode)(token, cookie_token=cookie_token)

        assert exc_info.value.clear_cookie is True

    async def test_expired_session_with_foreign_cookie_keeps_cookie(
        self, user_factory, cache_mode
    ):
        """Истёкшая сессия + чужая кука: срок не важен, кука не сверена.

        До правки сверка куки шла ПОСЛЕ проверки срока, и этот сценарий отдавал
        SessionExpired с удалением — гасил куку живой сессии.
        """

        user = await user_factory(login="expired_foreign")
        _, expired_token, _ = await _make_db_session(user.id, expired=True)
        _, _, live_cookie = await _make_db_session(user.id)

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await _check_by_token(cache_mode)(
                expired_token, cookie_token=live_cookie
            )

        assert exc_info.value.clear_cookie is False


class TestSessionCheckByCookieClearCookie:
    """session_check_by_cookie(_cached) — только кука, для вложений."""

    async def test_live_cookie_passes(self, user_factory, cache_mode):
        """Опорная точка: по живой куке сессия находится."""

        user = await user_factory(login="cookie_live")
        _, _, cookie_token = await _make_db_session(user.id)

        session = await _check_by_cookie(cache_mode)(cookie_token)

        assert session.user_id.id == user.id

    async def test_unknown_cookie_keeps_cookie(self, cache_mode):
        """По куке ничего не нашли — сирота могла быть уже перезаписана.

        delete_cookie удаляет по ИМЕНИ, а не по значению: снеся «ничью» куку,
        мы снесли бы ту, что только что положил свежий логин.
        """

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await _check_by_cookie(cache_mode)("definitely-not-a-cookie")

        assert exc_info.value.clear_cookie is False

    async def test_expired_session_clears_cookie(
        self, user_factory, cache_mode
    ):
        """Сессию нашли ПО САМОЙ куке — она точно её, удаление законно."""

        user = await user_factory(login="cookie_expired")
        _, _, cookie_token = await _make_db_session(user.id, expired=True)

        with pytest.raises(AuthException.SessionExpired) as exc_info:
            await _check_by_cookie(cache_mode)(cookie_token)

        assert exc_info.value.clear_cookie is True


class TestRevokedCachedEntry:
    """Ветка revoked есть только в кэше: в БД отозванная — «не найдена».

    Отозванную запись кладём в кэш напрямую: SessionCache.revoke() вычищает её
    из индексов, поэтому в тесте состояние «нашли и она revoked» иначе не
    воспроизвести (в бою оно возникает гонкой с держателем ссылки).
    """

    @pytest_asyncio.fixture
    async def revoked_entry(self):
        """Отозванная запись в кэше; отдаёт (token, cookie_token)."""

        token = secrets.token_urlsafe(64)
        cookie_token = secrets.token_urlsafe(64)
        now = datetime.now(timezone.utc)
        cache = AuthTokenApp.session_cache
        await cache.clear()
        await cache.put(
            CachedSession(
                session_id=1,
                user_id=1,
                is_admin=False,
                user_name="Revoked",
                lang_id=None,
                lang_code=None,
                cookie_token=cookie_token,
                token=token,
                # Срок ещё не вышел: иначе сработала бы ветка истечения.
                expired_datetime=now + timedelta(hours=1),
                ttl=3600,
                create_datetime=now,
                revoked=True,
            )
        )
        yield token, cookie_token
        await cache.clear()

    async def test_revoked_with_matching_cookie_clears_cookie(
        self, revoked_entry
    ):
        """Кука сверена до проверки revoked — значит она этой сессии."""

        token, cookie_token = revoked_entry

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await Session.session_check_cached(
                token, cookie_token=cookie_token
            )

        assert exc_info.value.clear_cookie is True

    async def test_revoked_with_foreign_cookie_keeps_cookie(
        self, revoked_entry
    ):
        """Чужая кука отсекается раньше revoked — удалять всё равно нельзя."""

        token, _ = revoked_entry

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await Session.session_check_cached(
                token, cookie_token="someone-elses-cookie"
            )

        assert exc_info.value.clear_cookie is False

    async def test_revoked_by_cookie_clears_cookie(self, revoked_entry):
        """Найдено ПО куке и отозвано — кука принадлежит этой сессии."""

        _, cookie_token = revoked_entry

        with pytest.raises(AuthException.SessionNotExist) as exc_info:
            await Session.session_check_by_cookie_cached(cookie_token)

        assert exc_info.value.clear_cookie is True


# ============================================================================
# Уровень HTTP: ради этого всё и делалось
# ============================================================================


class TestHttpGuardCookie:
    """Обработчик 401 удаляет куку только при exc.clear_cookie."""

    async def test_stale_tab_does_not_delete_live_cookie(
        self, client, test_env, user_factory, cache_mode
    ):
        """РЕГРЕСС: протухшая вкладка не должна разлогинивать живые.

        Кука в браузере одна: старая вкладка шлёт свой мёртвый Bearer вместе с
        АКТУАЛЬНОЙ кукой. Раньше ответ нёс delete_cookie — и соседние вкладки
        теряли куку, а с ней и сессию.
        """

        cookie_name = test_env.settings.auth.cookie_name
        user = await user_factory(login="two_tabs", is_admin=True)
        _, live_token, live_cookie = await _make_db_session(user.id)
        _, stale_token, _ = await _make_db_session(user.id, expired=True)

        client.headers["Authorization"] = f"Bearer {stale_token}"
        client.cookies.set(cookie_name, live_cookie)
        response = await client.post(SEARCH_URL, json=SEARCH_BODY)

        assert response.status_code == 401
        assert _guard_cookie_headers(response, cookie_name) == []

        # Соседняя вкладка продолжает работать — то, ради чего всё делалось.
        # Куку НЕ переставляем: пусть её несёт сам jar — только так проверка
        # сквозная, а не подсунутая руками.
        client.headers["Authorization"] = f"Bearer {live_token}"
        response = await client.post(SEARCH_URL, json=SEARCH_BODY)

        assert response.status_code == 200

    async def test_unknown_bearer_does_not_delete_cookie(
        self, client, test_env, user_factory, cache_mode
    ):
        """Bearer из отставшего localStorage не должен трогать чужую куку."""

        cookie_name = test_env.settings.auth.cookie_name
        user = await user_factory(login="http_unknown_bearer")
        _, _, live_cookie = await _make_db_session(user.id)

        client.headers["Authorization"] = "Bearer definitely-not-a-token"
        client.cookies.set(cookie_name, live_cookie)
        response = await client.post(SEARCH_URL, json=SEARCH_BODY)

        assert response.status_code == 401
        assert _guard_cookie_headers(response, cookie_name) == []

    async def test_missing_authorization_header_does_not_delete_cookie(
        self, client, test_env, user_factory, cache_mode
    ):
        """SessionErrorFormat (нет Bearer): куку не сверяли — не трогаем."""

        cookie_name = test_env.settings.auth.cookie_name
        user = await user_factory(login="http_no_header")
        _, _, live_cookie = await _make_db_session(user.id)

        client.cookies.set(cookie_name, live_cookie)
        response = await client.post(SEARCH_URL, json=SEARCH_BODY)

        assert response.status_code == 401
        assert _guard_cookie_headers(response, cookie_name) == []

    async def test_missing_cookie_does_not_send_delete(
        self, client, test_env, user_factory, cache_mode
    ):
        """SessionErrorFormat (нет куки): гасить нечего, Set-Cookie не нужен.

        Иначе ответ на запрос вкладки без куки убил бы куку у остальных.
        """

        cookie_name = test_env.settings.auth.cookie_name
        user = await user_factory(login="http_no_cookie")
        _, token, _ = await _make_db_session(user.id)

        client.headers["Authorization"] = f"Bearer {token}"
        response = await client.post(SEARCH_URL, json=SEARCH_BODY)

        assert response.status_code == 401
        assert _guard_cookie_headers(response, cookie_name) == []

    async def test_expired_session_with_own_cookie_deletes_cookie(
        self, client, test_env, user_factory, cache_mode
    ):
        """Парный позитив: своя кука + мёртвая сессия — удаление обязано быть.

        Без него браузер таскал бы бесполезную куку до конца max_age.
        """

        cookie_name = test_env.settings.auth.cookie_name
        user = await user_factory(login="http_expired_own")
        _, token, cookie_token = await _make_db_session(user.id, expired=True)

        client.headers["Authorization"] = f"Bearer {token}"
        client.cookies.set(cookie_name, cookie_token)
        response = await client.post(SEARCH_URL, json=SEARCH_BODY)

        assert response.status_code == 401
        headers = _guard_cookie_headers(response, cookie_name)
        assert headers, "ожидался Set-Cookie, удаляющий guard-куку"
        assert all(_is_deleting(header) for header in headers)

    async def test_successful_request_does_not_touch_cookie(
        self, client, test_env, user_factory, cache_mode
    ):
        """На успехе кука не переустанавливается: её ставит только /signin."""

        cookie_name = test_env.settings.auth.cookie_name
        user = await user_factory(login="http_live", is_admin=True)
        _, token, cookie_token = await _make_db_session(user.id)

        client.headers["Authorization"] = f"Bearer {token}"
        client.cookies.set(cookie_name, cookie_token)
        response = await client.post(SEARCH_URL, json=SEARCH_BODY)

        assert response.status_code == 200
        assert _guard_cookie_headers(response, cookie_name) == []


# ============================================================================
# Часовой: новое место выброса обязано осознанно выбрать clear_cookie
# ============================================================================

# Ожидаемые пары (исключение, clear_cookie) на каждый метод sessions.py.
# Порядок не важен — сравниваем отсортированные наборы. Тест падает и когда
# перевернули флаг, и когда ДОБАВИЛИ новый raise: у него надо осознанно решить,
# доказана ли принадлежность куки, и обновить матрицу в докстринге модуля.
EXPECTED_RAISES = {
    "session_check": [
        ("SessionExpired", True),
        ("SessionNotExist", False),  # токен не найден
        ("SessionNotExist", False),  # кука не совпала
    ],
    "session_check_by_cookie": [
        ("SessionExpired", True),
        ("SessionNotExist", False),  # по куке ничего не нашли
    ],
    "session_check_cached": [
        ("SessionExpired", True),
        ("SessionNotExist", False),  # токен не найден
        ("SessionNotExist", False),  # кука не совпала
        ("SessionNotExist", True),  # revoked, кука уже сверена
    ],
    "session_check_by_cookie_cached": [
        ("SessionExpired", True),
        ("SessionNotExist", False),  # по куке ничего не нашли
        ("SessionNotExist", True),  # revoked, нашли по самой куке
    ],
}


def _collect_raises(path: Path) -> dict[str, list[tuple[str, object]]]:
    """Пары (класс исключения, clear_cookie) по методам: raise AuthException.X.

    Разбор AST, а не строк: привязки к номерам строк нет, переименование или
    перенос кода теста не ломает.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    collected: dict[str, list[tuple[str, object]]] = {}

    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in _own_nodes(func):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            if not isinstance(call, ast.Call):
                continue
            func_ref = call.func
            if not isinstance(func_ref, ast.Attribute):
                continue
            owner = func_ref.value
            if not isinstance(owner, ast.Name) or owner.id != "AuthException":
                continue
            collected.setdefault(func.name, []).append(
                (func_ref.attr, _clear_cookie_arg(call))
            )

    return collected


def _own_nodes(func: ast.AST):
    """Узлы функции без вложенных def — чтобы не приписать чужой raise."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))
        yield node


def _clear_cookie_arg(call: ast.Call) -> object:
    """Значение clear_cookie у вызова; отсутствует — дефолт False.

    Не-литерал возвращаем как строку: сравнение упадёт, и это правильно —
    вычисляемый флаг надо смотреть глазами.
    """
    for keyword in call.keywords:
        if keyword.arg != "clear_cookie":
            continue
        if isinstance(keyword.value, ast.Constant):
            return keyword.value.value
        return ast.dump(keyword.value)
    return False


def test_clear_cookie_matrix_is_pinned():
    """Все места выброса AuthException в sessions.py — с ожидаемым флагом."""

    actual = _collect_raises(Path(sessions_module.__file__))

    assert {name: sorted(pairs) for name, pairs in actual.items()} == {
        name: sorted(pairs) for name, pairs in EXPECTED_RAISES.items()
    }


def test_auth_failed_keeps_cookie_by_default():
    """Дефолт — не удалять: забытый флаг не должен гасить чужие сессии."""

    assert AuthException.SessionNotExist().clear_cookie is False
    assert AuthException.SessionErrorFormat().clear_cookie is False
    assert AuthException.SessionExpired(clear_cookie=True).clear_cookie is True
