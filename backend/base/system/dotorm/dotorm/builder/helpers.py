"""Helper functions for SQL building."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..fields import Field


def build_sql_update_from_schema(
    sql: str,
    payload_dict: dict[str, Any],
    id: int | list[int],
    fields_map: "dict[str, Field]",
) -> tuple[str, tuple]:
    """Составляет запрос обновления (update).

    Для каждого поля вызывается field.to_sql_update(name, value) —
    поле само знает как себя представить в SET-клаузе. Обычные поля
    возвращают "field=%s", специальные (TranslatedChar) — свои конструкции
    типа jsonb_set(...). Билдер к типам полей равнодушен.

    Arguments:
        sql -- шаблон UPDATE с двумя %s (SET clause и WHERE clause)
        payload_dict -- сериализованные данные модели {field_name: value}
        id -- идентификатор или список идентификаторов для WHERE
        fields_map -- карта имя_поля → Field объект (из model._cache_all_fields)

    Returns:
        sql -- готовый SQL с плейсхолдерами
        values_list -- tuple значений для биндинга
    """
    if not payload_dict:
        raise ValueError("payload_dict cannot be empty")

    set_parts: list[str] = []
    values_list: list[Any] = []
    for field_name, value in payload_dict.items():
        field = fields_map[field_name]
        fragment, bind_value = field.to_sql_update(field_name, value)
        set_parts.append(fragment)
        values_list.append(bind_value)

    if isinstance(id, list):
        values_list.extend(id)
        where_placeholder = ", ".join(["%s"] * len(id))
    else:
        values_list.append(id)
        where_placeholder = "%s"

    query_placeholders = ", ".join(set_parts)
    sql = sql % (query_placeholders, where_placeholder)
    return sql, tuple(values_list)


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
