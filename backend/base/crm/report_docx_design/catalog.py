"""
Каталог полей шаблона для конструктора.

Конструктор (фронт) показывает список того, что можно вставить в DOCX, и по
клику ставит тег. Источника два, каталог их объединяет:

1. Поля модели записи (`report_type = record`): публичные поля модели, связи
   Many2one — на один уровень вглубь (partner_id.name), списки One2many /
   Many2many — как цикл по строкам таблицы. Их значения даёт общий контекст
   ReportTemplate.record_context.
2. Поля функций данных модели — то, что функции кладут в дикт сверх полей
   записи (bik, reciver, order_line…). Их объявляет декоратор @report_fields
   (report_docx.utils.fields) на самой функции; по этим ключам движок и
   вызывает функцию, если её тег стоит в шаблоне.

Каждый узел каталога несёт готовый тег (`tag`), а список — ещё начало и конец
цикла (`loop_start`/`loop_end`) для строки таблицы docxtpl. `kind` — источник
узла (field — поле записи, function — ключ функции данных), `type` — форма
значения (text/money/date/datetime/relation/list).
"""

from typing import Any, Callable

from backend.base.crm.report_docx.utils.fields import ReportField, ReportList
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import (
    Binary,
    Date,
    Datetime,
    Decimal,
    Float,
    Many2many,
    Many2one,
    One2many,
    PolymorphicMany2one,
    PolymorphicOne2many,
)

# Переменная цикла в строках-повторах: {%tr for item in rows %} … {{ item.x }}
LOOP_VAR = "item"

# Jinja-фильтры по типу поля (см. DocxReportEngine.jinja_env)
_FILTER_BY_TYPE = {"money": "money", "date": "date", "datetime": "datetime"}


def _tag(key: str, type: str | None) -> str:
    """Тег подстановки с фильтром по типу: {{ key|money }} / {{ key }}."""
    filter_name = _FILTER_BY_TYPE.get(type or "")
    return (
        f"{{{{ {key}|{filter_name} }}}}" if filter_name else f"{{{{ {key} }}}}"
    )


def _scalar_node(key: str, label: str, type: str | None, kind: str) -> dict:
    return {
        "key": key,
        "label": label,
        "type": type or "text",
        "kind": kind,
        "tag": _tag(key, type),
    }


def _list_node(key: str, label: str, children: list[dict], kind: str) -> dict:
    return {
        "key": key,
        "label": label,
        "type": "list",
        "kind": kind,
        "loop_start": f"{{%tr for {LOOP_VAR} in {key} %}}",
        "loop_end": "{%tr endfor %}",
        "children": children,
    }


# ------------------------------------------------------------------
# Поля модели
# ------------------------------------------------------------------


def _field_type(field: Any) -> str | None:
    if isinstance(field, (Decimal, Float)):
        return "money"
    if isinstance(field, Datetime):
        return "datetime"
    if isinstance(field, Date):
        return "date"
    return None


def _label(name: str, field: Any) -> str:
    return field.string or field.description or name


def _scalar_fields(model_cls) -> list[tuple[str, Any]]:
    """Публичные скалярные поля модели (без байтов, связей и полей с
    ролевым доступом — их нет и в контексте записи)."""
    return [
        (name, field)
        for name, field in model_cls.get_public_fields().items()
        if not field.relation
        and not isinstance(field, Binary)
        and not field._role_acl
    ]


def model_catalog(model_cls) -> list[dict]:
    """Каталог полей записи модели: скаляры, Many2one на один уровень,
    One2many/Many2many как списки со скалярами элемента."""
    nodes: list[dict] = []
    for name, field in _scalar_fields(model_cls):
        nodes.append(
            _scalar_node(
                name, _label(name, field), _field_type(field), "field"
            )
        )

    for name, field in model_cls.get_public_fields().items():
        if (
            not field.relation
            or field._role_acl
            or isinstance(field, (PolymorphicOne2many, PolymorphicMany2one))
        ):
            continue
        related = field.relation_table
        if related is None:
            continue
        if isinstance(field, Many2one):
            children = [
                _scalar_node(
                    f"{name}.{sub}",
                    _label(sub, sub_field),
                    _field_type(sub_field),
                    "field",
                )
                for sub, sub_field in _scalar_fields(related)
            ]
            nodes.append(
                {
                    "key": name,
                    "label": _label(name, field),
                    "type": "relation",
                    "kind": "field",
                    "tag": _tag(f"{name}.name", None),
                    "children": children,
                }
            )
        elif isinstance(field, (One2many, Many2many)):
            children = [
                _scalar_node(
                    f"{LOOP_VAR}.{sub}",
                    _label(sub, sub_field),
                    _field_type(sub_field),
                    "field",
                )
                for sub, sub_field in _scalar_fields(related)
            ]
            nodes.append(
                _list_node(name, _label(name, field), children, "field")
            )
    return nodes


# ------------------------------------------------------------------
# Поля функции данных
# ------------------------------------------------------------------


def _split_spec(spec: "str | ReportField") -> tuple[str, str | None]:
    if isinstance(spec, ReportField):
        return spec.label, spec.type
    return str(spec), None


def function_catalog(func: Callable | None) -> list[dict]:
    """Узлы из @report_fields функции данных (пусто, если не объявлены)."""
    declared: dict = getattr(func, "_report_fields", None) or {}
    nodes: list[dict] = []
    for key, spec in declared.items():
        if isinstance(spec, ReportList):
            children = []
            for sub, sub_spec in spec.fields.items():
                sub_label, sub_type = _split_spec(sub_spec)
                children.append(
                    _scalar_node(
                        f"{LOOP_VAR}.{sub}", sub_label, sub_type, "function"
                    )
                )
            nodes.append(_list_node(key, spec.label, children, "function"))
        else:
            label, type = _split_spec(spec)
            nodes.append(_scalar_node(key, label, type, "function"))
    return nodes


# ------------------------------------------------------------------
# Каталог шаблона
# ------------------------------------------------------------------


async def template_field_catalog(template_id: int) -> list[dict]:
    """Поля функций данных модели (@report_fields) + поля записи модели
    (для документа по записи) шаблона. Сводному шаблону записи нет —
    функции документа по записи ему не предлагаются."""
    templates = env.models.report_template
    tmpl = await templates.get_template(template_id)
    model_cls = templates.resolve_model(tmpl.model_name)
    with_record = tmpl.report_type != "summary"
    nodes = [
        node
        for func in templates.data_functions(model_cls, with_record)
        for node in function_catalog(func)
    ]
    if with_record:
        nodes += model_catalog(model_cls)
    return nodes
