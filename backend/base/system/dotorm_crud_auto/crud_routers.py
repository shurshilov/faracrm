import asyncio
from typing import Any, Callable, Literal, Type, Union

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import create_model
from starlette.status import HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST

from backend.base.system.dotorm_crud_auto.crud_pydantic_schemas import (
    SchemaCreateOutput,
    SchemaGetOutput,
    SchemaSearchOutput,
)
from backend.base.system.dotorm.dotorm.model import JsonMode
from backend.base.system.dotorm.dotorm.integrations.pydantic import (
    dotorm_to_pydantic_nested_one,
)
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.schemas.base_schema import Id

# TODO: удалить зависимость от байс
from backend.base.crm.auth_token.app import AuthTokenApp

from backend.base.system.dotorm_crud_auto.crud_pydantic_types import (
    OmitId,
    Partial,
    RelationNestedPickIdName,
    RelationNestedSearch,
    RelationNestedUpdateCreate,
    RelationOmitX2M,
    create_class,
    generate_search_triplet,
)


class CRUDRouterGenerator(APIRouter):
    def __init__(
        self,
        Model: Type[DotModel],
        search_route: bool = True,
        create_route: bool = True,
        update_route: bool = True,
        delete_route: bool = True,
        get_route: bool = True,
        **kwargs: Any,
    ) -> None:
        self.Model = Model
        self.env = env
        try:
            self.__schema_update__ = self.Model.__schema_update__
        except:
            # self.__schema_update__ = type(
            #     self.Model.__name__ + "Update",
            #     (
            #         self.Model.__schema__,
            #         Partial,
            #         OmitId,
            #         RelationNestedUpdateCreate,
            #     ),
            #     {"model_config": ConfigDict(protected_namespaces=())},
            # )
            self.__schema_update__ = create_class(
                self.Model.__name__ + "Update",
                self.Model.__schema__,
                Partial,
                OmitId,
                RelationNestedUpdateCreate,
            )

        try:
            self.__schema_create__ = self.Model.__schema_create__
        except:
            # self.__schema_create__ = type(
            #     self.Model.__name__ + "Create",
            #     (self.Model.__schema__, OmitId, RelationNestedUpdateCreate),
            #     {"model_config": ConfigDict(protected_namespaces=())},
            # )
            self.__schema_create__ = create_class(
                self.Model.__name__ + "Create",
                self.Model.__schema__,
                OmitId,
                RelationNestedUpdateCreate,
            )

        try:
            self.__schema_read_output__ = self.Model.__schema_read_output__
        except:
            # на 2 уровне вложености оставить только поля name и id
            # это значит что любое поле m2m или o2m, внутри любого поля m2m или o2m
            # будет содержать только эти два поля
            # Partial делает все поля опциональными т.к. клиент может запросить любой набор
            self.__schema_read_output__ = create_class(
                self.Model.__name__,
                self.Model.__schema__,
                Partial,
                RelationNestedSearch,
            )
            self.__schema_read_partial_output__ = create_class(
                self.Model.__name__ + "Partial",
                self.Model.__schema__,
                Partial,
                RelationNestedSearch,
            )

        try:
            self.__schema_read_search_output__ = (
                self.Model.__schema_read_search_output__
            )
        except:
            # на 1 уровне вложеноости оставить только поля name и id
            # это значит что любое поле m2m или o2m будет содержать только эти два поля
            # self.__schema_read_search_output__ = type(
            #     self.Model.__name__ + "ReadSearchOutput",
            #     (self.Model.__schema__, Partial, RelationNestedPickIdName),
            #     {"model_config": ConfigDict(protected_namespaces=())},
            # )
            self.__schema_read_search_output__ = create_class(
                self.Model.__name__ + "ReadSearchOutput",
                self.Model.__schema__,
                Partial,
                # RelationOmitX2M,
                RelationNestedPickIdName,
            )

        allowed_fields = list(self.Model.get_fields())
        triplet_fields = generate_search_triplet(self.Model.__schema__)
        SchemaSearchInput = create_model(
            self.Model.__name__ + "SearchInput",
            fields=(list[Literal[*allowed_fields]], ...),
            end=(int | None, None),
            order=(Literal["DESC", "ASC", "desc", "asc"], "DESC"),
            sort=(Literal[*allowed_fields], "id"),
            start=(int | None, None),
            limit=(int, 80),
            # filter=(shema_field_search | None, None),
            filter=(list[Union[*triplet_fields]], None),
            # filter=(Annotated[list[Union[*triplet_fields]], Query(None)]),
            raw=(bool, False),
        )

        self.__schema_read_search_input__ = SchemaSearchInput
        # self.__schema_read_search_input__ = type(
        #     self.Model.__name__ + "ReadSearchInput",
        #     (SchemaSearchInput,),
        #     {},
        # )

        super().__init__(**kwargs)

        if search_route:
            self.add_api_route(
                f"{self.Model.__route__}/search",
                self.search(),
                response_model=SchemaSearchOutput[
                    list[self.__schema_read_search_output__]
                ],
                response_model_exclude=self.Model.__response_model_exclude__,
                response_model_exclude_unset=True,
                methods=["POST"],
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )
            self.add_api_route(
                f"{self.Model.__route__}/search_many2many",
                self.search_many2many(),
                # response_model=SchemaSearchOutput[
                #     list[self.__schema_read_search_output__]
                # ],
                # response_model_exclude=self.Model.__response_model_exclude__,
                # response_model_exclude_unset=True,
                methods=["GET"],
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )

        # Эндпоинт для получения списка полей модели (для фильтрации)
        # ВАЖНО: должен быть ДО /{id} роутов чтобы не конфликтовать
        print(
            f"[CRUDRouterGenerator] Adding /fields route for {self.Model.__route__}"
        )
        self.add_api_route(
            f"{self.Model.__route__}/fields",
            self.get_model_fields(),
            methods=["GET"],
            dependencies=[Depends(AuthTokenApp.verify_access)],
        )
        print(f"[CRUDRouterGenerator] Added /fields route")

        if create_route:
            self.add_api_route(
                f"{Model.__route__}",
                self.create(),
                methods=["POST"],
                response_model=SchemaCreateOutput,
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )
            self.add_api_route(
                f"{Model.__route__}/default_values",
                self.create_default_values(),
                methods=["POST"],
                response_model_exclude=self.Model.__response_model_exclude__,
                response_model_exclude_unset=True,
                # response_model=SchemaSearchOutput[self.__schema_update__],
                # response_model=SchemaGetOutput[self.__schema_update__],
                response_model=SchemaGetOutput[
                    self.__schema_read_partial_output__
                ],
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )
        if update_route:
            self.add_api_route(
                f"{Model.__route__}/{{id}}",
                self.update(),
                methods=["PUT"],
                response_model_exclude=self.Model.__response_model_exclude__,
                response_model_exclude_unset=True,
                response_model=self.__schema_update__,
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )
        if delete_route:
            self.add_api_route(
                f"{Model.__route__}/bulk",
                self.delete_bulk(),
                methods=["DELETE"],
                response_model=Literal[True],
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )
            self.add_api_route(
                f"{Model.__route__}/{{id}}",
                self.delete(),
                methods=["DELETE"],
                response_model=Literal[True],
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )
        if get_route:
            self.add_api_route(
                f"{Model.__route__}/{{id}}",
                self.get(),
                methods=["POST"],
                response_model=SchemaGetOutput[self.__schema_read_output__],
                response_model_exclude=self.Model.__response_model_exclude__,
                # response_model_exclude_none=True,
                response_model_exclude_unset=True,
                dependencies=[Depends(AuthTokenApp.verify_access)],
            )

    def get_model_fields(self, *args: Any, **kwargs: Any) -> Callable:
        """Возвращает список полей модели с их типами для фильтрации."""
        Model = self.Model

        async def route():
            # Используем существующий метод, передавая все поля
            all_fields = list(Model.get_fields().keys())
            return Model.get_fields_info_list(all_fields)

        return route

    def delete(self, *args: Any, **kwargs: Any) -> Callable:
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

    def delete_bulk(self, *args: Any, **kwargs: Any) -> Callable:
        Model = self.Model

        async def route(ids: list[int]):
            await Model.delete_bulk(ids)
            return True

        return route

    def get(self, *args: Any, **kwargs: Any) -> Callable:
        """Роут одиночной записи. РЕСТ синглтон.

        Returns:
            одну запись (объект)
        """
        Model = self.Model
        # allowed_fields = list(Model.get_fields())
        allowed_fields = dotorm_to_pydantic_nested_one(Model)

        async def route(id: int, payload: allowed_fields):  # type: ignore
            # список полей которые запросил клиент
            # список всех полей, которые нужны клиенту
            fields_client = []
            # поля отношений, со списком вложенных полей
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
            fields_info = {field["name"]: field for field in fields_info}

            response_data = record.json(
                include=set(fields_client), mode=JsonMode.FORM
            )

            # Обернуть O2M/M2M в {data, fields, total} для UI
            from backend.base.system.dotorm_crud_auto.crud_routers_v2 import (
                _wrap_relations_for_ui,
            )

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

    def update(self, *args: Any, **kwargs: Any) -> Callable:
        """
        RFC 5789.
        "patch document"
        If the entire patch document
        cannot be successfully applied, then the server MUST NOT apply any of
        the changes.
        ...
        The PATCH method affects the resource identified by the Request-URI, and it
        also MAY have side effects on other resources; i.e., new resources
        may be created, or existing ones modified, by the application of a
        PATCH.
        ...

        Its mean must be transaction.
        """
        Model = self.Model
        schema_input_update = self.__schema_update__

        async def route(id: Id, payload: schema_input_update):  # type: ignore
            record = await Model.get(id)
            if not record:
                return JSONResponse(
                    content={"error": "#NOT_FOUND"},
                    status_code=HTTP_404_NOT_FOUND,
                )
            payload_dict = payload.model_dump(exclude_unset=True)
            fields_names = list(payload_dict)
            payload: DotModel = Model(**payload_dict)
            await record.update(payload, fields_names)

            return payload_dict

        return route

    def create(self, *args: Any, **kwargs: Any) -> Callable:
        Model = self.Model
        schema_input_create = self.__schema_create__

        async def route(payload: schema_input_create):  # type: ignore
            payload_dict = payload.model_dump(exclude_unset=True)

            fields_names = list(payload_dict)
            payload: DotModel = Model(**payload_dict)
            id = await Model.create(Model(**payload_dict))
            record = await Model.get(id)
            if record:
                # заменить виртуальный ИД на созданный только что
                await record.update(payload, fields_names)
            return {"id": id}

        return route

    def create_default_values(self, *args: Any, **kwargs: Any) -> Callable:
        Model = self.Model
        allowed_fields = dotorm_to_pydantic_nested_one(Model)

        async def route(payload: allowed_fields):  # type: ignore
            # список всех полей, которые нужны клиенту
            fields_client = []
            # поля отношений, со списком вложенных полей
            fields_client_nested = {}

            for field in payload.fields:
                if isinstance(field, str):
                    fields_client.append(field)
                else:
                    field_relation: dict[str, list[str]] = field.model_dump()
                    for (
                        field_relation_name,
                        field_relation_nested_fields,
                    ) in field_relation.items():
                        fields_client.append(field_relation_name)
                        fields_client_nested[field_relation_name] = (
                            field_relation_nested_fields
                        )

            default_values = await Model.get_default_values(
                fields_client_nested
            )
            # fields_client = list(default_values)
            fields_info = Model.get_fields_info_form(fields_client)

            fields_info = {field["name"]: field for field in fields_info}
            return {
                # "data": record.json(include=set(fields_client), mode=JsonMode.FORM),
                "data": default_values,
                "fields": fields_info,
            }
            # return default_values

        return route

    def search_many2many(self, *args: Any, **kwargs: Any) -> Callable:
        Model = self.Model
        allowed_fields = list(Model.get_relation_fields_m2m())

        if not allowed_fields:
            allowed_fields_m2m = None
        else:
            allowed_fields_m2m = Literal[*allowed_fields]

        async def route(
            id: Id,
            name: allowed_fields_m2m,  # type: ignore
            fields: list[str] = Query(),
            order: Literal["desc", "asc"] = "desc",
            start: int | None = None,
            end: int | None = None,
            sort: str = Query("id"),
            limit: int = 40,
        ):
            field_class = getattr(Model, name)

            (
                records,
                count_total,
            ) = await asyncio.gather(
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

    def search(self, *args: Any, **kwargs: Any) -> Callable:
        """Роут поиск с пагинацией. РЕСТ коллекция.

        Returns:
            список обьектов модели с пагинацией
        """
        Model = self.Model
        schema_read_search_input = self.__schema_read_search_input__

        async def route(
            # payload: Annotated[schema_read_search_input, Query()],
            payload: schema_read_search_input,
        ):
            allowed_fields = Model.get_fields().keys()
            for field in payload.fields:
                if field not in allowed_fields:
                    return JSONResponse(
                        content={"error": "#FIELDS_NOT_FOUND"},
                        status_code=HTTP_400_BAD_REQUEST,
                    )

            (
                records,
                count_total,
            ) = await asyncio.gather(
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
