"""
Упрощённый генератор CRUD роутеров.

Использует SchemaRegistry для получения готовых схем вместо
генерации их в __init__ каждого роутера.
"""

import asyncio
from typing import Any, Callable, Literal, Type

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from starlette.status import HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST

from backend.base.system.dotorm_crud_auto.crud_pydantic_schemas import (
    SchemaCreateOutput,
    SchemaGetOutput,
    SchemaSearchOutput,
)
from backend.base.system.dotorm.dotorm.model import DotModel, JsonMode
from backend.base.system.dotorm.dotorm.integrations.pydantic import (
    dotorm_to_pydantic_nested_one,
)
from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.schemas.base_schema import Id

from .schema_registry import SchemaRegistry


class CRUDRouterGenerator(APIRouter):
    """
    Генератор CRUD роутеров для DotModel.

    Использует готовые схемы из SchemaRegistry.
    """

    def __init__(
        self,
        Model: Type[DotModel],
        schema_registry: SchemaRegistry,
        search_route: bool = True,
        create_route: bool = True,
        update_route: bool = True,
        delete_route: bool = True,
        get_route: bool = True,
        **kwargs: Any,
    ) -> None:
        self.Model = Model
        self.registry = schema_registry

        # Получаем готовые схемы из реестра
        self._schema_create = schema_registry.get_create_schema(Model)
        self._schema_update = schema_registry.get_update_schema(Model)
        self._schema_search_output = schema_registry.get_search_output_schema(
            Model
        )
        self._schema_read_output = schema_registry.get_read_output_schema(
            Model
        )
        self._schema_search_input = schema_registry.get_search_input_schema(
            Model
        )

        super().__init__(**kwargs)

        # Регистрируем роуты
        # ВАЖНО: /fields должен быть ДО /{id} роутов
        self._add_fields_route()

        if search_route:
            self._add_search_routes()
        if create_route:
            self._add_create_routes()
        if update_route:
            self._add_update_routes()
        if delete_route:
            self._add_delete_routes()
        if get_route:
            self._add_get_routes()

    def _add_fields_route(self) -> None:
        """Добавляет роут для получения списка полей модели."""
        self.add_api_route(
            f"{self.Model.__route__}/fields",
            self._get_fields(),
            methods=["GET"],
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )

    def _add_search_routes(self) -> None:
        """Добавляет роуты поиска."""
        self.add_api_route(
            f"{self.Model.__route__}/search",
            self._search(),
            response_model=SchemaSearchOutput[
                list[self._schema_search_output]
            ],
            response_model_exclude=self.Model.__response_model_exclude__,
            response_model_exclude_unset=True,
            methods=["POST"],
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )
        self.add_api_route(
            f"{self.Model.__route__}/search_many2many",
            self._search_many2many(),
            methods=["GET"],
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )

    def _add_create_routes(self) -> None:
        """Добавляет роуты создания."""
        self.add_api_route(
            f"{self.Model.__route__}",
            self._create(),
            methods=["POST"],
            response_model=SchemaCreateOutput,
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )
        self.add_api_route(
            f"{self.Model.__route__}/default_values",
            self._create_default_values(),
            methods=["POST"],
            response_model_exclude=self.Model.__response_model_exclude__,
            response_model_exclude_unset=True,
            response_model=SchemaGetOutput[self._schema_read_output],
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )

    def _add_update_routes(self) -> None:
        """Добавляет роуты обновления."""
        self.add_api_route(
            f"{self.Model.__route__}/{{id}}",
            self._update(),
            methods=["PUT"],
            response_model_exclude=self.Model.__response_model_exclude__,
            response_model_exclude_unset=True,
            response_model=self._schema_update,
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )

    def _add_delete_routes(self) -> None:
        """Добавляет роуты удаления."""
        self.add_api_route(
            f"{self.Model.__route__}/bulk",
            self._delete_bulk(),
            methods=["DELETE"],
            response_model=Literal[True],
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )
        self.add_api_route(
            f"{self.Model.__route__}/{{id}}",
            self._delete(),
            methods=["DELETE"],
            response_model=Literal[True],
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )

    def _add_get_routes(self) -> None:
        """Добавляет роуты получения."""
        self.add_api_route(
            f"{self.Model.__route__}/{{id}}",
            self._get(),
            methods=["POST"],
            response_model=SchemaGetOutput[self._schema_read_output],
            response_model_exclude=self.Model.__response_model_exclude__,
            response_model_exclude_unset=True,
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )

    # ==================== Handlers ====================

    def _search(self) -> Callable:
        """Поиск с пагинацией."""
        Model = self.Model
        schema_input = self._schema_search_input

        async def route(payload: schema_input):  # type: ignore
            allowed_fields = Model.get_all_fields().keys()
            for field in payload.fields:
                if field not in allowed_fields:
                    return JSONResponse(
                        content={"error": "#FIELDS_NOT_FOUND"},
                        status_code=HTTP_400_BAD_REQUEST,
                    )

            records, count_total = await asyncio.gather(
                Model.search(**payload.model_dump()),
                Model.search_count(filter=payload.filter),
            )

            if not payload.raw:
                records = [rec.json(include=payload.fields) for rec in records]

            fields_info = Model.get_fields_info_list(payload.fields)

            return {
                "data": records,
                "total": str(count_total),
                "fields": fields_info,
            }

        return route

    def _search_many2many(self) -> Callable:
        """Поиск Many2Many связей."""
        Model = self.Model
        allowed_fields = list(Model.get_relation_fields_m2m())

        if not allowed_fields:
            allowed_fields_literal = None
        else:
            allowed_fields_literal = Literal[tuple(allowed_fields)]

        async def route(
            id: Id,
            name: allowed_fields_literal,  # type: ignore
            fields: list[str] = Query(),
            order: Literal["desc", "asc"] = "desc",
            start: int | None = None,
            end: int | None = None,
            sort: str = Query("id"),
            limit: int = 40,
        ):
            field_class = getattr(Model, name)

            records, count_total = await asyncio.gather(
                Model.get_many2many(
                    id,
                    field_class.relation_table,
                    field_class.many2many_table,
                    field_class.column1,
                    field_class.column2,
                    fields,
                    order,
                    start,
                    end,
                    sort,
                    limit,
                ),
                Model.get_many2many(
                    id,
                    field_class.relation_table,
                    field_class.many2many_table,
                    field_class.column1,
                    field_class.column2,
                    ["id"],
                    "desc",
                    None,
                    None,
                    "id",
                    None,
                ),
            )

            fields_info = field_class.relation_table.get_fields_info_list(
                fields
            )
            return {
                "data": records,
                "total": str(len(count_total)),
                "fields": fields_info,
            }

        return route

    def _create(self) -> Callable:
        """Создание записи."""
        Model = self.Model
        schema_input = self._schema_create

        async def route(payload: schema_input):  # type: ignore
            payload_dict = payload.model_dump(exclude_unset=True)
            fields_names = list(payload_dict)
            model_instance = Model(**payload_dict)

            id = await Model.create(model_instance)
            record = await Model.get(id)

            if record:
                await record.update_with_relations(
                    model_instance, fields_names
                )

            return {"id": id}

        return route

    def _create_default_values(self) -> Callable:
        """Получение значений по умолчанию."""
        Model = self.Model
        allowed_fields = dotorm_to_pydantic_nested_one(Model)

        async def route(payload: allowed_fields):  # type: ignore
            fields_client = []
            fields_client_nested = {}

            for field in payload.fields:
                if isinstance(field, str):
                    fields_client.append(field)
                else:
                    field_relation: dict = field.model_dump()
                    for name, nested_fields in field_relation.items():
                        fields_client.append(name)
                        fields_client_nested[name] = nested_fields

            default_values = await Model.get_default_values(
                fields_client_nested
            )
            fields_info = Model.get_fields_info_form(fields_client)
            fields_info = {f["name"]: f for f in fields_info}

            return {
                "data": default_values,
                "fields": fields_info,
            }

        return route

    def _update(self) -> Callable:
        """Обновление записи."""
        Model = self.Model
        schema_input = self._schema_update

        async def route(id: Id, payload: schema_input):  # type: ignore
            record = await Model.get(id)
            if not record:
                return JSONResponse(
                    content={"error": "#NOT_FOUND"},
                    status_code=HTTP_404_NOT_FOUND,
                )

            payload_dict = payload.model_dump(exclude_unset=True)
            fields_names = list(payload_dict)
            model_instance = Model(**payload_dict)

            await record.update_with_relations(model_instance, fields_names)

            return payload_dict

        return route

    def _delete(self) -> Callable:
        """Удаление записи."""
        Model = self.Model

        async def route(id: int):
            record = await Model.get(id)
            if not record:
                return JSONResponse(
                    content={"error": "#NOT_FOUND"},
                    status_code=HTTP_404_NOT_FOUND,
                )
            await record.delete()
            return True

        return route

    def _delete_bulk(self) -> Callable:
        """Массовое удаление."""
        Model = self.Model

        async def route(ids: list[int]):
            await Model.delete_bulk(ids)
            return True

        return route

    def _get(self) -> Callable:
        """Получение записи."""
        Model = self.Model
        allowed_fields = dotorm_to_pydantic_nested_one(Model)

        async def route(id: int, payload: allowed_fields):  # type: ignore
            fields_client = []
            fields_client_nested = {}

            for field in payload.fields:
                if isinstance(field, str):
                    fields_client.append(field)
                else:
                    field_relation = field.model_dump()
                    for key, val in field_relation.items():
                        fields_client.append(key)
                        fields_client_nested[key] = val

            record = await Model.get(
                id,
                fields=fields_client,
                fields_nested=fields_client_nested,
            )

            if not record:
                return JSONResponse(
                    content={"error": "#NOT_FOUND"},
                    status_code=HTTP_404_NOT_FOUND,
                )

            fields_info = Model.get_fields_info_form(fields_client)
            fields_info = {f["name"]: f for f in fields_info}

            response_data = record.json(
                include=set(fields_client), mode=JsonMode.FORM
            )

            # Обернуть O2M/M2M в {data, fields, total} для UI
            await _wrap_relations_for_ui(
                Model,
                record,
                response_data,
                fields_client,
                fields_client_nested,
            )

            return {
                "data": response_data,
                "fields": fields_info,
            }

        return route

    def _get_fields(self) -> Callable:
        """Получение списка полей модели для фильтрации."""
        Model = self.Model

        async def route():
            all_fields = list(Model.get_fields().keys())
            return Model.get_fields_info_list(all_fields)

        return route


async def _wrap_relations_for_ui(
    Model,
    record,
    response_data: dict,
    fields_client: list[str],
    fields_client_nested: dict[str, list[str]],
):
    """
    Обернуть O2M/M2M поля в {data, fields, total} формат для UI.

    Используется после get(fields_nested=...) для формирования
    ответа, совместимого с фронтендом (пагинация таблиц).
    search_count запросы выполняются параллельно.
    """
    from backend.base.system.dotorm.dotorm.fields import (
        Many2many,
        One2many,
        PolymorphicOne2many,
    )

    # Собираем информацию и корутины для параллельного выполнения
    wrap_items = []  # (name, nested, rel_fields_info, count_coro | int)

    for name, field_cls in Model.get_relation_fields():
        if name not in fields_client:
            continue
        if not isinstance(
            field_cls, (Many2many, One2many, PolymorphicOne2many)
        ):
            continue

        value = getattr(record, name)
        if not isinstance(value, list):
            continue

        nested = fields_client_nested.get(name)
        if not nested and field_cls.relation_table:
            nested = ["id"]
            if field_cls.relation_table.get_fields().get("name"):
                nested.append("name")
            if isinstance(field_cls, PolymorphicOne2many):
                nested = field_cls.relation_table.get_store_fields_omit_m2o()

        rel_fields_info = field_cls.relation_table.get_fields_info_list(
            nested or ["id"]
        )

        # Готовим count — корутину или значение
        if isinstance(field_cls, One2many):
            count = field_cls.relation_table.search_count(
                filter=[(field_cls.relation_table_field, "=", record.id)]
            )
        elif isinstance(field_cls, PolymorphicOne2many):
            count = field_cls.relation_table.search_count(
                filter=[
                    ("res_id", "=", record.id),
                    ("res_model", "=", record.__table__),
                ]
            )
        else:
            count = len(value)

        wrap_items.append((name, rel_fields_info, count))

    if not wrap_items:
        return

    # Собираем корутины для параллельного выполнения
    coros = []
    coro_indices = []
    totals = [None] * len(wrap_items)

    for i, (name, rel_fields_info, count) in enumerate(wrap_items):
        if asyncio.iscoroutine(count):
            coro_indices.append(i)
            coros.append(count)
        else:
            totals[i] = count

    if coros:
        results = await asyncio.gather(*coros)
        for idx, result in zip(coro_indices, results):
            totals[idx] = result

    # Применяем
    for i, (name, rel_fields_info, _) in enumerate(wrap_items):
        response_data[name] = {
            "data": response_data.get(name, []),
            "fields": rel_fields_info,
            "total": totals[i],
        }
