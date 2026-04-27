# Copyright 2025 FARA CRM
# Security — Custom rule operators (SQL-fragment based, v4)
#
# Расширяет систему rules спец-операторами:
#   ("@is_member", target_field, member_table, member_field, [active_field])
#   ("@has_parent_access", parent_model, fk_field)
#   ("@has_polymorphic_parent_access", model_field, id_field)
#
# Операторы возвращают SqlFragment (готовый SQL+values), который
# FilterParser подставляет напрямую в финальный запрос. Никакой
# материализации id'шников в Python — всё через subquery'и в БД.
#
# Производительность: один SQL-запрос для всех проверок доступа,
# БД сама оптимизирует через semi-joins. Работает на любых объёмах.

import logging
from typing import Any, Awaitable, Callable

from backend.base.system.dotorm.dotorm.components.filter_parser import (
    SqlFragment,
)
from backend.base.system.dotorm.dotorm.access import (
    get_access_checker,
    Operation,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Реестр операторов
# ─────────────────────────────────────────────────────────────────

OperatorFn = Callable[[list, dict], Awaitable[Any]]
_OPERATORS: dict[str, OperatorFn] = {}


def register_operator(name: str):
    def decorator(fn: OperatorFn) -> OperatorFn:
        if not name.startswith("@"):
            raise ValueError(f"Operator name must start with '@': {name}")
        _OPERATORS[name] = fn
        return fn

    return decorator


def is_operator_triplet(expr: Any) -> bool:
    return (
        isinstance(expr, (list, tuple))
        and len(expr) >= 1
        and isinstance(expr[0], str)
        and expr[0].startswith("@")
    )


# ─────────────────────────────────────────────────────────────────
# Резолвер: разворачивает операторы в SqlFragment'ы / обычные triplets
# ─────────────────────────────────────────────────────────────────

_MAX_RECURSION_DEPTH = 5
_request_cache: dict[int, dict] = {}


def _get_or_create_cache(user_id: int) -> dict:
    if user_id not in _request_cache:
        _request_cache[user_id] = {}
    return _request_cache[user_id]


def clear_cache(user_id: int | None = None) -> None:
    """
    Очистить кэш операторов.
    Вызвать при изменении membership / rules / ACL.
    """
    if user_id is None:
        _request_cache.clear()
    else:
        _request_cache.pop(user_id, None)


async def resolve_operators(
    domain: Any,
    user_id: int,
    env,
    current_model: str | None = None,
    cache: dict | None = None,
    _seen_models: tuple[str, ...] = (),
    _depth: int = 0,
) -> Any:
    """
    Рекурсивно обходит domain, заменяя @-операторы на SqlFragment
    или обычные triplets.

    Returns:
        Domain где @-операторы заменены готовыми выражениями.
        Парсер потом скомпилирует это в финальный SQL.
    """
    if _depth > _MAX_RECURSION_DEPTH:
        raise RuntimeError(
            f"rule operator recursion too deep "
            f"(>{_MAX_RECURSION_DEPTH}), seen: {_seen_models}"
        )

    if cache is None:
        cache = _get_or_create_cache(user_id)

    # Уже скомпилированный SqlFragment (от рекурсивного резолва) —
    # проходим как есть
    if isinstance(domain, SqlFragment):
        return domain

    # Не контейнер — просто значение
    if not isinstance(domain, (list, tuple)):
        return domain

    # @-operator triplet
    if is_operator_triplet(domain):
        op_name = domain[0]
        op_args = list(domain[1:])

        if op_name not in _OPERATORS:
            raise ValueError(f"Unknown rule operator: {op_name}")

        ctx = {
            "user_id": user_id,
            "env": env,
            "cache": cache,
            "current_model": current_model,
            "seen_models": _seen_models,
            "depth": _depth + 1,
        }
        resolved = await _OPERATORS[op_name](op_args, ctx)
        # Оператор мог вернуть SqlFragment, обычный triplet,
        # или ещё один domain с операторами (рекурсия)
        return await resolve_operators(
            resolved,
            user_id,
            env,
            current_model,
            cache,
            _seen_models,
            _depth + 1,
        )

    # Обычный triplet (не @)
    if (
        len(domain) == 3
        and isinstance(domain[0], str)
        and not domain[0].startswith("@")
    ):
        return list(domain)

    # NOT expression
    if (
        len(domain) == 2
        and isinstance(domain[0], str)
        and domain[0].lower() == "not"
    ):
        inner = await resolve_operators(
            domain[1],
            user_id,
            env,
            current_model,
            cache,
            _seen_models,
            _depth + 1,
        )
        return ["not", inner]

    # Список с возможными AND/OR
    result = []
    for item in domain:
        if isinstance(item, str) and item.lower() in ("and", "or"):
            result.append(item)
        else:
            result.append(
                await resolve_operators(
                    item,
                    user_id,
                    env,
                    current_model,
                    cache,
                    _seen_models,
                    _depth + 1,
                )
            )
    return result


# ─────────────────────────────────────────────────────────────────
# Операторы
# ─────────────────────────────────────────────────────────────────


@register_operator("@is_member")
async def is_member(args: list, ctx: dict):
    """
    Membership-фильтр через subquery.

    Args:
        target_field: поле в текущей модели куда подставится IN
        member_table: имя member-таблицы
        member_field: поле в member-таблице которое сравнивается с target
        active_field: опционально, имя поля is_active или None

    Возвращает:
        SqlFragment с подзапросом:
            "target_field" IN (
                SELECT member_field FROM member_table
                WHERE user_id = $1 [AND active_field = TRUE]
            )

    Пример:
        ("@is_member", "id", "chat_member", "chat_id")
        →
        '"id" IN (SELECT "chat_id" FROM "chat_member"
                  WHERE "user_id" = %s AND "is_active" = TRUE)'
        с values = [user_id]
    """
    if len(args) < 3 or len(args) > 4:
        raise ValueError(
            "@is_member expects 3 or 4 args: "
            "(target_field, member_table, member_field, [active_field])"
        )

    target_field = args[0]
    member_table = args[1]
    member_field = args[2]
    active_field = args[3] if len(args) == 4 else "is_active"

    user_id = ctx["user_id"]

    cache = ctx.get("cache")
    cache_key = (
        "is_member",
        user_id,
        target_field,
        member_table,
        member_field,
        active_field,
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    # Строим SQL-фрагмент с subquery
    sql = (
        f'"{target_field}" IN ('
        f'SELECT "{member_field}" FROM "{member_table}" '
        f'WHERE "user_id" = %s'
    )
    values: list = [user_id]
    if active_field:
        sql += f' AND "{active_field}" = TRUE'
    sql += ")"

    result = SqlFragment(sql, values)
    if cache is not None:
        cache[cache_key] = result
    return result


@register_operator("@has_parent_access")
async def has_parent_access(args: list, ctx: dict):
    """
    Parent-access фильтр через рекурсивный subquery.

    Использование:
        ("@has_parent_access", "chat_message", "message_id")

    Возвращает:
        SqlFragment:
            "message_id" IN (
                SELECT id FROM "chat_message"
                WHERE <скомпилированные rules chat_message>
            )

    Rules родителя получаются через checker._get_domains, рекурсивно
    резолвятся (вложенные @-операторы тоже становятся SqlFragment'ами),
    компилируются через FilterParser в SQL-фрагмент. Всё внутри одного
    финального запроса — никаких отдельных SELECT'ов в Python.
    """
    if len(args) != 2:
        raise ValueError(
            "@has_parent_access expects 2 args: (parent_model, fk_field)"
        )

    parent_model_name = args[0]
    fk_field = args[1]

    seen = ctx["seen_models"]
    if parent_model_name in seen:
        raise RuntimeError(
            f"@has_parent_access recursion through {parent_model_name}, "
            f"seen path: {seen + (parent_model_name,)}"
        )

    user_id = ctx["user_id"]
    env = ctx["env"]

    cache = ctx.get("cache")
    cache_key = ("has_parent_access", user_id, parent_model_name, fk_field)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    # parent_model_name может быть именем класса или таблицы
    parent_cls = getattr(env.models, parent_model_name, None)
    if parent_cls is None:
        try:
            parent_cls = env.models._get_model_class_by_table(
                parent_model_name
            )
            parent_model_name = env.models._get_model_name_by_table(
                parent_model_name
            )
        except KeyError:
            parent_cls = None

    if parent_cls is None:
        result = SqlFragment("FALSE", [])
        if cache is not None:
            cache[cache_key] = result
        return result

    checker = get_access_checker()
    role_ids = await checker._get_user_roles(user_id)

    has_acl = await checker._check_acl(
        role_ids, parent_model_name, Operation.READ
    )
    if not has_acl:
        result = SqlFragment("FALSE", [])
        if cache is not None:
            cache[cache_key] = result
        return result

    # Получаем rules родителя — _get_domains их уже зарезолвит через
    # resolve_operators (см. интеграцию в access_control). Вернётся
    # domain с SqlFragment'ами и обычными triplet'ами.
    parent_domain = await checker._get_domains(
        role_ids, parent_model_name, Operation.READ, user_id
    )

    parent_table = parent_cls.__table__

    if not parent_domain:
        # У родителя нет rules → возвращаем все его записи через ACL
        # Subquery без WHERE — все id таблицы
        sql = f'"{fk_field}" IN (SELECT id FROM "{parent_table}")'
        result = SqlFragment(sql, [])
    else:
        # Компилируем domain родителя в SQL через парсер
        # Получаем filter_parser той же модели — он работает с её
        # полями и dialect'ом
        parser = parent_cls._builder.filter_parser
        rules_sql, rules_values = parser.parse(parent_domain)

        sql = (
            f'"{fk_field}" IN ('
            f'SELECT id FROM "{parent_table}" '
            f"WHERE {rules_sql})"
        )
        result = SqlFragment(sql, list(rules_values))

    if cache is not None:
        cache[cache_key] = result
    return result


@register_operator("@has_polymorphic_parent_access")
async def has_polymorphic_parent_access(args: list, ctx: dict):
    """
    Полиморфный parent-access фильтр.

    Использование:
        ("@has_polymorphic_parent_access", "res_model", "res_id")

    Возвращает один большой SqlFragment с OR по всем встретившимся
    res_model:

        (
            (res_model = 'chat_message' AND res_id IN (SELECT id FROM chat_message WHERE ...))
            OR
            (res_model = 'partner' AND res_id IN (SELECT id FROM partner))
            OR
            ...
        )

    Один запрос за DISTINCT res_model + сборка большого SQL.
    Никакой материализации, никаких параллельных запросов —
    всё в одном финальном SQL который БД оптимизирует.
    """
    if len(args) != 2:
        raise ValueError(
            "@has_polymorphic_parent_access expects 2 args: "
            "(model_field, id_field)"
        )

    model_field = args[0]
    id_field = args[1]

    user_id = ctx["user_id"]
    env = ctx["env"]
    current_model_name = ctx.get("current_model")
    if not current_model_name:
        raise RuntimeError(
            "@has_polymorphic_parent_access needs current_model in ctx"
        )

    cache = ctx.get("cache")
    cache_key = (
        "has_polymorphic_parent_access",
        user_id,
        current_model_name,
        model_field,
        id_field,
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    current_cls = getattr(env.models, current_model_name, None)
    if current_cls is None:
        try:
            current_cls = env.models._get_model_class_by_table(
                current_model_name
            )
        except KeyError:
            current_cls = None
    if current_cls is None:
        result = SqlFragment("FALSE", [])
        if cache is not None:
            cache[cache_key] = result
        return result

    # Один маленький запрос — какие res_model встречаются.
    # На composite-индексе (res_model, res_id) это Index Skip Scan,
    # миллисекунды даже на миллионе записей.
    table_name = current_cls.__table__
    db_session = current_cls._get_db_session()
    distinct_sql = (
        f'SELECT DISTINCT "{model_field}" AS m '
        f'FROM "{table_name}" '
        f'WHERE "{model_field}" IS NOT NULL'
    )
    rows = await db_session.execute(distinct_sql)
    res_models = [r["m"] for r in rows]

    if not res_models:
        result = SqlFragment("FALSE", [])
        if cache is not None:
            cache[cache_key] = result
        return result

    checker = get_access_checker()
    role_ids = await checker._get_user_roles(user_id)

    # Собираем OR-блоки.
    # Для каждой res_model:
    #   (res_model = 'X' AND res_id IN (SELECT id FROM X_table WHERE rules))
    or_parts: list[str] = []
    or_values: list = []

    for res_model_name in res_models:
        # Определяем класс родителя
        parent_cls = getattr(env.models, res_model_name, None)
        if parent_cls is None:
            try:
                parent_cls = env.models._get_model_class_by_table(
                    res_model_name
                )
                parent_model_class_name = env.models._get_model_name_by_table(
                    res_model_name
                )
            except KeyError:
                logger.debug(
                    "polymorphic: no model registered for table '%s'",
                    res_model_name,
                )
                continue
        else:
            parent_model_class_name = res_model_name

        # ACL родителя
        try:
            has_acl = await checker._check_acl(
                role_ids, parent_model_class_name, Operation.READ
            )
        except Exception:
            continue
        if not has_acl:
            continue

        # Rules родителя (могут содержать вложенные @-операторы —
        # они уже зарезолвлены внутри _get_domains)
        try:
            parent_domain = await checker._get_domains(
                role_ids, parent_model_class_name, Operation.READ, user_id
            )
        except Exception:
            parent_domain = None

        parent_table = parent_cls.__table__
        block_sql = (
            f'("{model_field}" = %s AND "{id_field}" IN ('
            f'SELECT id FROM "{parent_table}"'
        )
        block_values: list = [res_model_name]

        if parent_domain:
            # Компилируем rules родителя в SQL
            parser = parent_cls._builder.filter_parser
            rules_sql, rules_values = parser.parse(parent_domain)
            block_sql += f" WHERE {rules_sql}"
            block_values.extend(rules_values)

        block_sql += "))"

        or_parts.append(block_sql)
        or_values.extend(block_values)

    if not or_parts:
        result = SqlFragment("FALSE", [])
    elif len(or_parts) == 1:
        result = SqlFragment(or_parts[0], or_values)
    else:
        # Объединяем через OR, оборачиваем в скобки на всякий случай
        joined = " OR ".join(or_parts)
        result = SqlFragment(f"({joined})", or_values)

    if cache is not None:
        cache[cache_key] = result
    return result
