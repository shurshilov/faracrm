"""Helper functions for SQL building."""

from __future__ import annotations
from typing import Any


def build_sql_update_from_schema(
    sql: str,
    payload_dict: dict[str, Any],
    id: int | list[int],
) -> tuple[str, tuple]:
    """Составляет запрос обновления (update).

    Arguments:
        sql -- текст шаблона запроса
        payload_dict -- сериализованные данные модели
        id -- идентификатор или список идентификаторов

    Returns:
        sql -- текст запроса с подстановками (биндингами)
        values_list -- значения для биндинга
    """
    if not payload_dict:
        raise ValueError("payload_dict cannot be empty")

    fields_list, values_list = zip(*payload_dict.items())
    values_list = tuple(values_list)

    if isinstance(id, list):
        values_list += tuple(id)
        where_placeholder = ", ".join(["%s"] * len(id))
    else:
        values_list += (id,)
        where_placeholder = "%s"

    query_placeholders = ", ".join(f"{field}=%s" for field in fields_list)
    sql = sql % (query_placeholders, where_placeholder)
    return sql, values_list


def build_sql_create_from_schema(
    sql: str,
    payload_dict: dict[str, Any],
) -> tuple[str, tuple]:
    """Составляет запрос создания (insert).

    Arguments:
        sql -- текст шаблона запроса
        payload_dict -- сериализованные данные модели

    Returns:
        sql -- текст запроса с подстановками (биндингами)
        values_list -- значения для биндинга
    """
    if not payload_dict:
        raise ValueError("payload_dict cannot be empty")

    fields_list, values_list = zip(*payload_dict.items())

    query_columns = ", ".join(fields_list)
    query_placeholders = ", ".join(["%s"] * len(values_list))
    sql = sql % (query_columns, query_placeholders)
    return sql, values_list
