# Copyright 2025 FARA CRM
# Excel — экспорт выборки списка в .xlsx и импорт записей из .xlsx
#
# Работает с любой моделью автокруда по имени таблицы (как /auto/{model}).
# Формат технический: заголовки — имена полей, связи и вложения — id.
# Доступ штатный: чтение — Model.search (ACL и правила строк), запись —
# Model.create + update связей, как у create-роута автокруда, чтобы
# переопределения моделей (канонизация контактов, прогресс по стадии)
# срабатывали как при создании из формы.

import base64
import datetime
import logging
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.access import AccessDenied
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Many2many,
    Many2one,
    PolymorphicMany2one,
)

from .. import xlsx
from ..download import download_all

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.system.dotorm.dotorm.model import DotModel

log = logging.getLogger(__name__)

router_private = APIRouter(
    tags=["Excel"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)

# Экспорт читает записи страницами — память не зависит от размера выборки.
EXPORT_PAGE = 1000
# Имён на один запрос резолва связи (OR по =ilike).
RESOLVE_CHUNK = 200


class ExportRequest(BaseModel):
    fields: list[str]
    filter: list | None = None
    sort: str = "id"
    order: Literal["asc", "desc"] = "asc"
    # Выбранные в списке записи — вместо фильтра.
    ids: list[int] | None = None


class ExcelFile(BaseModel):
    content: str  # .xlsx в base64


class ImportRequest(ExcelFile):
    mapping: dict[int, str]  # индекс колонки файла → имя поля


def _error(content: str, detail: str, status_code: int = 400) -> FaraException:
    return FaraException(
        {"content": content, "detail": detail, "status_code": status_code}
    )


def _model(req: Request, model: str) -> "type[DotModel]":
    """Модель по имени таблицы с фронта. Только с автокрудом: у моделей,
    закрытых от /auto/…, и здесь доступа нет."""
    env: "Environment" = req.app.state.env
    try:
        Model = env.models._get_model_class_by_table(model)
    except KeyError:
        Model = None
    if Model is None or not Model.__auto_crud__:
        raise _error("#NOT_FOUND", f"Модель «{model}» не найдена", 404)
    return Model


def _decode(content: str) -> bytes:
    try:
        return base64.b64decode(content, validate=True)
    except ValueError as e:
        raise _error("#EXCEL_BAD_FILE", f"Не удалось прочитать файл: {e}")


def _read_file(content: bytes) -> tuple[list[str], xlsx.Rows]:
    """Заголовки и строки первого листа; любой сбой разбора — это не
    .xlsx."""
    try:
        return xlsx.read_sheet(content)
    except Exception as e:  # noqa: BLE001
        raise _error("#EXCEL_BAD_FILE", f"Не удалось прочитать файл: {e}")


@router_private.post("/excel/{model}/export")
async def export_excel(req: Request, model: str, payload: ExportRequest):
    """Выборка списка (или выбранные ids) → .xlsx: заголовки — имена
    полей, связи — id через запятую."""
    Model = _model(req, model)
    fields = xlsx.exportable_fields(Model)
    names = payload.fields
    unknown = [name for name in names if name not in fields]
    if not names or unknown:
        raise _error(
            "#EXCEL_BAD_FIELDS",
            f"Нет таких полей: {', '.join(unknown) or '—'}",
        )
    # У связей нужны только id — иначе search тянет все столбцы
    # связанной таблицы.
    nested = {
        name: {"fields": ["id"]} for name in names if fields[name].relation
    }
    filter = (
        [("id", "in", payload.ids)]
        if payload.ids is not None
        else payload.filter
    )
    sort = payload.sort if payload.sort in Model.get_store_fields() else "id"

    rows: list[list] = []
    offset = 0
    while True:
        try:
            records = await Model.search(
                fields=names,
                fields_nested=nested or None,
                filter=filter,
                sort=sort,
                order=payload.order,
                start=offset,
                end=offset + EXPORT_PAGE,
            )
        except ValueError as e:
            # FilterParser: неизвестное поле или оператор в фильтре.
            raise _error("#FILTER_INVALID", str(e))
        rows.extend(
            [
                xlsx.to_cell(fields[name], getattr(record, name))
                for name in names
            ]
            for record in records
        )
        if len(records) < EXPORT_PAGE:
            break
        offset += EXPORT_PAGE

    filename = quote(f"{model}_{datetime.date.today():%Y-%m-%d}.xlsx", safe="")
    return Response(
        content=xlsx.build_workbook(names, rows),
        media_type=xlsx.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{filename}"
        },
    )


@router_private.post("/excel/{model}/preview")
async def preview_excel(req: Request, model: str, payload: ExcelFile):
    """Разбор файла: колонки (заголовок + примеры значений) и поля модели,
    которые можно заполнить, — для сопоставления в интерфейсе."""
    Model = _model(req, model)
    headers, rows = _read_file(_decode(payload.content))
    importable = xlsx.importable_fields(Model)
    by_lower = {name.lower(): name for name in importable}
    columns = [
        {
            "index": index,
            "header": header,
            # Поле по заголовку без режима «(name)» — автосопоставление.
            "field": by_lower.get(xlsx.parse_header(header)[0].lower()),
            "samples": [
                xlsx.text(cells[index])
                for _, cells in rows[:3]
                if index < len(cells) and cells[index] is not None
            ],
        }
        for index, header in enumerate(headers)
        if header
    ]
    return {
        "columns": columns,
        "rows_total": len(rows),
        "fields": Model.get_fields_info_list(list(importable)),
    }


@router_private.post("/excel/{model}/import")
async def import_excel(req: Request, model: str, payload: ImportRequest):
    """Создать записи по сопоставлению «колонка → поле».

    Связь ищется по id; заголовок «uom_id (name)» в файле переключает
    колонку на поиск по полю name связанной модели (любое её текстовое
    поле: name, code, login). Строки с ошибками разбора (не число, нет
    такого варианта, связь не найдена, файл не скачался, пустое
    обязательное поле) пропускаются и возвращаются в errors; остальные
    создаются одной транзакцией — сбой на записи в БД откатывает весь
    импорт.
    """
    env: "Environment" = req.app.state.env
    Model = _model(req, model)
    importable = xlsx.importable_fields(Model)
    mapping = {index: name for index, name in payload.mapping.items() if name}
    unknown = [name for name in mapping.values() if name not in importable]
    if not mapping or unknown or len(set(mapping.values())) != len(mapping):
        raise _error(
            "#EXCEL_BAD_MAPPING",
            "Поля нельзя импортировать или указаны дважды: "
            f"{', '.join(unknown) or '—'}",
        )
    info = {f["name"]: f for f in Model.get_fields_info_list(list(importable))}
    required = [name for name in importable if info[name]["required"]]
    missing = [name for name in required if name not in mapping.values()]
    if missing:
        raise _error(
            "#EXCEL_REQUIRED_FIELDS",
            f"Не сопоставлены обязательные поля: {', '.join(missing)}",
        )

    content = _decode(payload.content)
    headers, rows = _read_file(content)
    # Поле поиска связи — из заголовка колонки в файле («(name)»).
    lookup = {
        index: (
            xlsx.parse_header(headers[index])[1]
            if index < len(headers)
            else "id"
        )
        for index in mapping
    }
    for index, name in mapping.items():
        field = importable[name]
        by = lookup[index]
        if (
            by != "id"
            and isinstance(field, (Many2one, Many2many))
            and not isinstance(
                field.relation_table.get_public_fields().get(by), Char
            )
        ):
            raise _error(
                "#EXCEL_BAD_MAPPING",
                f"{name}: у связанной модели нет текстового поля «{by}»",
            )
    attachment_names = [
        name
        for name in mapping.values()
        if isinstance(importable[name], PolymorphicMany2one)
    ]
    # Картинки в ячейках — только если вложение вообще сопоставлено:
    # для них файл читается второй раз, уже целиком.
    pictures: dict = {}
    if attachment_names:
        pictures = _read_pictures(
            content,
            [
                index
                for index, name in mapping.items()
                if name in attachment_names
            ],
        )

    # 1. Ячейки → значения по типу поля (связи пока сырыми: id или имя,
    # вложения — id или URL; картинка в ячейке — вместо пустого значения).
    errors: list[dict] = []
    parsed: list[tuple[int, dict]] = []  # (номер строки в файле, значения)
    for row_number, cells in rows:
        values: dict = {}
        errors_before = len(errors)
        for index, name in mapping.items():
            cell = cells[index] if index < len(cells) else None
            try:
                value = xlsx.from_cell(importable[name], cell)
            except ValueError as e:
                errors.append(
                    {"row": row_number, "field": name, "message": str(e)}
                )
                continue
            if value is None:
                value = pictures.get((row_number, index))
            if value is not None:
                values[name] = value
        for name in required:
            if name not in values:
                errors.append(
                    {
                        "row": row_number,
                        "field": name,
                        "message": "не заполнено обязательное поле",
                    }
                )
        if len(errors) == errors_before:
            parsed.append((row_number, values))

    # 2. Связи: id проверяются на существование, а при поиске по полю
    # («(name)») текст → id; один-два запроса на поле. Many2one — запись,
    # Many2many — список id.
    for index, name in mapping.items():
        field = importable[name]
        if not isinstance(field, (Many2one, Many2many)):
            continue
        by = lookup[index]
        raw: set = set()
        for _, values in parsed:
            if name in values:
                raw.update(_tokens(values[name]))
        found = await _resolve_relation(field.relation_table, raw, by)
        kept: list[tuple[int, dict]] = []
        for row_number, values in parsed:
            if name in values:
                tokens = _tokens(values[name])
                lost = [token for token in tokens if token not in found]
                if lost:
                    message = "не найдено: " + ", ".join(
                        str(token) for token in lost
                    )
                    if by == "id" and any(
                        isinstance(token, str) for token in lost
                    ):
                        message += (
                            " (это не id; для поиска по названию укажите "
                            f"в заголовке «{name} (name)»)"
                        )
                    errors.append(
                        {"row": row_number, "field": name, "message": message}
                    )
                    continue
                ids = [found[token] for token in tokens]
                values[name] = (
                    ids
                    if isinstance(field, Many2many)
                    else field.relation_table(id=ids[0])
                )
            kept.append((row_number, values))
        parsed = kept

    # 3. Вложения: id — связать существующее, URL — скачать, картинка из
    # ячейки — как есть. Новые вложения — словарём полей, как шлёт форма;
    # res_id подставит update.
    if attachment_names:
        parsed = await _resolve_attachments(
            Model, importable, attachment_names, parsed, errors
        )

    # 4. Создание — одной транзакцией, через create: переопределения
    # моделей срабатывают как при создании из формы; Many2many (список id)
    # и вложения create пишет сам после INSERT.
    created = 0
    async with env.apps.db.get_transaction():
        for row_number, values in parsed:
            try:
                await Model.create(Model(**values))
            except AccessDenied:
                raise
            except Exception as e:  # noqa: BLE001 — откат всего импорта
                detail = (
                    e.args[0].get("detail") or e.args[0].get("content")
                    if isinstance(e, FaraException)
                    else str(e)
                )
                log.warning("Excel import %s row %s: %s", model, row_number, e)
                raise _error(
                    "#EXCEL_IMPORT_FAILED", f"Строка {row_number}: {detail}"
                ) from e
            created += 1

    errors.sort(key=lambda item: item["row"])
    return {"created": created, "errors": errors}


def _tokens(value) -> list:
    """Сырое значение связи из ячейки → список ссылок (id или имён)."""
    return value if isinstance(value, list) else [value]


def _read_pictures(content: bytes, columns: list[int]) -> dict:
    """Картинки листа в колонках вложений → {(строка, колонка): поля
    вложения без res_model}."""
    try:
        images = xlsx.read_images(content)
    except Exception as e:  # noqa: BLE001
        raise _error("#EXCEL_BAD_FILE", f"Не удалось прочитать файл: {e}")
    return {
        (row_number, column): {
            "name": f"row{row_number}.{fmt}",
            "mimetype": f"image/{fmt}",
            "size": len(data),
            "content": data,
        }
        for (row_number, column), (data, fmt) in images.items()
        if column in columns
    }


async def _resolve_attachments(
    Model, importable, names: list[str], parsed: list, errors: list
) -> list:
    """Значения колонок-вложений → запись вложения (id) или поля нового
    (URL скачан, картинка из ячейки). Не скачалось / нет такого id —
    ошибка строки."""
    urls = {
        values[name]
        for _, values in parsed
        for name in names
        if isinstance(values.get(name), str)
    }
    downloaded = await download_all(urls) if urls else {}
    for name in names:
        Attachment = importable[name].relation_table
        ids = {
            values[name]
            for _, values in parsed
            if isinstance(values.get(name), int)
        }
        found = await _resolve_relation(Attachment, ids) if ids else {}
        kept = []
        for row_number, values in parsed:
            value = values.get(name)
            if isinstance(value, int):
                if value not in found:
                    errors.append(
                        {
                            "row": row_number,
                            "field": name,
                            "message": f"не найдено вложение {value}",
                        }
                    )
                    continue
                values[name] = Attachment(id=value)
            elif isinstance(value, str):
                file = downloaded[value]
                if isinstance(file, str):
                    errors.append(
                        {"row": row_number, "field": name, "message": file}
                    )
                    continue
                values[name] = {**file, "res_model": Model.__table__}
            elif isinstance(value, dict):
                values[name] = {**value, "res_model": Model.__table__}
            kept.append((row_number, values))
        parsed = kept
    return parsed


async def _resolve_relation(Relation, raw_values: set, by: str = "id") -> dict:
    """Сырые значения ячеек → id записи связанной модели. by="id" —
    числа, проверяются на существование (текст не ищется); иначе — по
    текстовому полю by связанной модели без учёта регистра (число в
    ячейке — тоже текст). Ненайденных в ответе нет."""
    found: dict = {}
    if by == "id":
        ids = sorted(value for value in raw_values if isinstance(value, int))
        if ids:
            records = await Relation.search(
                fields=["id"], filter=[("id", "in", ids)]
            )
            found.update((record.id, record.id) for record in records)
        return found
    texts = {value: str(value).lower() for value in raw_values}
    by_text: dict[str, int] = {}
    unique = sorted(set(texts.values()))
    for start in range(0, len(unique), RESOLVE_CHUNK):
        clause: list = []
        for text in unique[start : start + RESOLVE_CHUNK]:
            if clause:
                clause.append("or")
            clause.append((by, "=ilike", Relation._dialect.like_escape(text)))
        # Группа в скобках: правила доступа приклеиваются по И.
        records = await Relation.search(fields=["id", by], filter=[clause])
        for record in records:
            by_text.setdefault(str(getattr(record, by)).lower(), record.id)
    for value, text in texts.items():
        if text in by_text:
            found[value] = by_text[text]
    return found
