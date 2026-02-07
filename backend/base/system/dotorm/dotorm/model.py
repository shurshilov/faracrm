"""DotModel - main ORM model class."""

from abc import ABCMeta
import asyncio
from enum import IntEnum
import json
from types import UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Type,
    Union,
    dataclass_transform,
    get_origin,
    get_args,
)


from .components.dialect import POSTGRES, Dialect

if TYPE_CHECKING:
    from .builder.builder import Builder
    import aiomysql
    import asyncpg

    # import asynch


# from .databases.mysql.session import (
#     NoTransactionSession as MysqlNoTransactionSession,
# )
from .databases.postgres.session import (
    NoTransactionSession as PostgresNoTransactionSession,
)

# from .databases.clickhouse.session import (
#     NoTransactionSession as ClickhouseNoTransactionSession,
# )

from .fields import (
    PolymorphicOne2many,
    Field,
    JSONField,
    Many2many,
    Many2one,
    One2many,
    One2one,
    PolymorphicMany2one,
)


class JsonMode(IntEnum):
    FORM = 1
    LIST = 2
    CREATE = 3
    UPDATE = 4
    NESTED_LIST = 5  # Для вложенных записей внутри FORM


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class ModelMetaclass(ABCMeta): ...


# Import mixins here to avoid circular imports
from .orm.mixins.ddl import DDLMixin
from .orm.mixins.primary import OrmPrimaryMixin
from .orm.mixins.many2many import OrmMany2manyMixin
from .orm.mixins.relations import OrmRelationsMixin
from .orm.mixins.access import AccessMixin


class DotModel(
    DDLMixin,
    OrmRelationsMixin,
    OrmMany2manyMixin,
    OrmPrimaryMixin,
    AccessMixin,
    metaclass=ModelMetaclass,
):
    """
    Main ORM model class.

    Combines all functionality through mixins:
    - OrmPrimaryMixin: Basic CRUD operations (create, get, update, delete)
    - OrmMany2manyMixin: Many-to-many relation operations
    - OrmRelationsMixin: Search and relation loading
    - DDLMixin: Table creation (DDL operations)

    Example:
        from dotorm import DotModel, Integer, Char, Many2one
        from dotorm.components import POSTGRES

        class User(DotModel):
            __table__ = "users"
            _dialect = POSTGRES

            id: int = Integer(primary_key=True)
            name: str = Char(max_length=100)
            role_id: int = Many2one(lambda: Role)

        # CRUD operations
        user = await User.get(1)
        users = await User.search(fields=["id", "name"], limit=10)
        new_id = await User.create(User(name="John"))
        await user.update(User(name="Jane"))
        await user.delete()

        # DDL operations
        await User.__create_table__()
    """

    # class variables (it is intended to be shared by all instances)
    # name of table in database
    __table__: ClassVar[str]
    # create table in db
    __auto_create__: ClassVar[bool] = True
    # path name for route ednpoints CRUD
    __route__: ClassVar[str]
    # create CRUD endpoints automaticaly or not
    __auto_crud__: ClassVar[bool] = False
    # name database
    __database__: ClassVar[str]
    # pool of connections to database
    # use for default usage in orm (without explicit set)
    _pool: ClassVar["asyncpg.Pool | None"]
    # class that implement no transaction execute
    # single connection -> execute -> release connection to pool
    # use for default usage in orm (without explicit set)
    _no_transaction: Type[PostgresNoTransactionSession] = (
        PostgresNoTransactionSession
    )
    # base validation schema for routers endpoints
    # __schema__: ClassVar[Type]
    __schema__: ClassVar[Any]
    # variables for override auto created - update and create schemas
    __schema_create__: ClassVar[Type]
    __schema_read_output__: ClassVar[Type]
    __schema_read_search_output__: ClassVar[Type]
    __schema_read_search_input__: ClassVar[Type]
    __schema_update__: ClassVar[Type]
    __response_model_exclude__: ClassVar[set[str] | None] = None
    # its auto
    # __schema_output_search__: ClassVar[Type]

    # id required field in any model
    id: ClassVar[int]

    _dialect: ClassVar[Dialect] = POSTGRES
    _builder: ClassVar["Builder"]

    def __init_subclass__(cls, **kwargs):
        """
        1.Срабатывает один раз при определении подкласса,а не при каждом создании экземпляра
        2.Позволяет устанавливать значения на уровне класса, а не объекта
        3.__init_subclass__ — это правильный и "официальный"
        способ кастомизировать поведение наследования
        """
        # не забудем super на случай MRO
        super().__init_subclass__(**kwargs)
        # Здесь мы проверяем не hasattr, а __dict__,
        # чтобы не словить унаследованный __route__
        if "__table__" in cls.__dict__ and "__route__" not in cls.__dict__:
            # установить имя роута такой же как имя модели по умолчанию
            cls.__route__ = "/" + cls.__table__

        # Lazy field cache — built on first access via _ensure_field_cache()
        cls._cache_all_fields: dict[str, Field] | None = None
        cls._cache_store_fields: list[str] | None = None
        cls._cache_store_fields_dict: dict[str, Field] | None = None
        cls._cache_json_fields: list[str] | None = None
        cls._cache_compute_fields: list[tuple[str, Field]] | None = None
        cls._cache_has_json_fields: bool | None = None
        cls._cache_has_compute_fields: bool | None = None

    @classmethod
    def _ensure_field_cache(cls):
        """Build field cache once (lazy). Called from __init__ and prepare_list_ids."""
        if cls._cache_all_fields is not None:
            return
        fields = {}
        for klass in reversed(cls.__mro__):
            if klass is object:
                continue
            for attr_name, attr in klass.__dict__.items():
                if isinstance(attr, Field):
                    fields[attr_name] = attr
        cls._cache_all_fields = fields
        cls._cache_store_fields = [
            name for name, field in fields.items() if field.store
        ]
        cls._cache_store_fields_dict = {
            name: field for name, field in fields.items() if field.store
        }
        cls._cache_json_fields = [
            name
            for name, field in fields.items()
            if isinstance(field, JSONField)
        ]
        cls._cache_compute_fields = [
            (name, field)
            for name, field in fields.items()
            if field.compute and not field.store
        ]
        cls._cache_has_json_fields = bool(cls._cache_json_fields)
        cls._cache_has_compute_fields = bool(cls._cache_compute_fields)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Fast path: bulk-assign all kwargs via __dict__
        self.__dict__.update(kwargs)

        cls = self.__class__
        cls._ensure_field_cache()

        # Десериализация JSON полей (если пришла строка из БД)
        # asyncpg не десериализует jsonb автоматически без кодека,
        # поэтому нужен fallback json.loads для строковых значений.
        if cls._cache_has_json_fields:
            for name in cls._cache_json_fields:
                value = self.__dict__.get(name)
                if isinstance(value, str):
                    try:
                        self.__dict__[name] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        pass

        # Вычисляемые поля (compute, не хранящиеся в БД)
        if cls._cache_has_compute_fields:
            for name, field in cls._cache_compute_fields:
                self.__dict__[name] = field.compute(self)

    #             # Если есть функция вычисления (имя метода)
    #             if isinstance(field.compute, str):
    #                 # Проверяем, существует ли метод
    #                 method_name = field.compute
    #                 if hasattr(self, method_name):
    #                     # Вычисляем значение сразу
    #                     method = getattr(self, method_name)
    #                     if hasattr(method, "compute_deps"):
    #                         # Для методов с зависимостями - не вычисляем сразу
    #                         # а оставляем как не вычисленное
    #                         pass
    #                     else:
    #                         # Вычисляем значение
    #                         setattr(self, name, method())
    #                 else:
    #                     raise AttributeError(
    #                         f"Method '{method_name}' not found for field '{name}'"
    #                     )

    # def __setattr__(self, name: str, value: Any) -> None:
    #     """Переопределяем для отслеживания изменений"""
    #     # Если это поле модели и оно изменилось
    #     if name in self.get_fields():
    #         field = self.get_fields()[name]
    #         if field.store:  # Только если поле хранится в БД
    #             # Инвалидируем зависимые поля
    #             self._invalidate_dependent_fields(name)
    #     super().__setattr__(name, value)

    # def _invalidate_dependent_fields(self, changed_field: str):
    #     """Инвалидировать все зависимые поля"""
    #     # Проходим по всем полям модели
    #     for field_name, field in self.get_fields().items():
    #         # Если это вычисляемое поле с зависимостями
    #         if field.compute and not field.store:
    #             method_name = field.compute
    #             if isinstance(method_name, str) and hasattr(self, method_name):
    #                 method = getattr(self, method_name)
    #                 # Проверяем, есть ли зависимости
    #                 if hasattr(method, "compute_deps"):
    #                     deps = method.compute_deps
    #                     if changed_field in deps:
    #                         # Устанавливаем флаг, что поле нужно пересчитать
    #                         # Вместо удаления атрибута - устанавливаем флаг
    #                         setattr(self, f"_{field_name}_computed", False)

    @classmethod
    def _get_db_session(cls, session=None):
        """
        Получить сессию БД.

        Приоритет:
        1. Явно переданная session
        2. Сессия из контекста транзакции (contextvars)
        3. NoTransaction сессия (автокоммит)
        """
        if session is not None:
            return session

        # Проверяем контекст транзакции
        from .databases.postgres.transaction import get_current_session

        ctx_session = get_current_session()
        if ctx_session is not None:
            return ctx_session

        # Fallback на NoTransaction
        return cls._no_transaction(cls._pool)

    @classmethod
    def prepare_form_id(cls, r: list):
        """Deserialize from dict to object."""
        if not r:
            return None
        if len(r) > 1:
            raise Exception("More than 1 record in form")
        record = cls(**r[0])
        return record

    @classmethod
    def prepare_list_ids(cls, rows: list):
        """Десериализация из списка записей (dict или asyncpg Record) в список объектов.

        Fast path: bypasses __init__ when model has no JSON/compute fields.
        Uses object.__new__ + __dict__.update — same approach as SQLAlchemy.
        """
        cls._ensure_field_cache()
        # Fast path: no JSON deserialization, no compute fields
        if (
            not cls._cache_has_json_fields
            and not cls._cache_has_compute_fields
        ):
            result = []
            for r in rows:
                obj = object.__new__(cls)
                obj.__dict__.update(r)
                result.append(obj)
            return result
        # Slow path: has JSON or compute fields — use full __init__
        return [cls(**r) for r in rows]

    @classmethod
    def prepare_list_id(cls, r: list):
        """Десериализация из словаря в объект.
        Используется при получении данных из БД.
        Заменяет m2o с объекта Model на {id:Model}
        Заменяет m2m и o2m с списка Model на list[{id:Model}]
        """
        if len(r) != 1:
            raise
        record = cls(**r[0])
        return record

    @classmethod
    def get_fields(cls) -> dict[str, Field]:
        """Возвращает все поля модели, включая унаследованные из миксинов.

        Использует кэш для избежания MRO traversal на каждом вызове.
        """
        cls._ensure_field_cache()
        return cls._cache_all_fields

    @classmethod
    def get_own_fields(cls) -> dict[str, Field]:
        """Возвращает только собственные поля класса (без унаследованных).

        Для получения всех полей включая унаследованные используйте get_fields().
        """
        return {
            attr_name: attr
            for attr_name, attr in cls.__dict__.items()
            if isinstance(attr, Field)
        }

    @classmethod
    def get_all_fields(cls) -> dict[str, Field]:
        """
        Возвращает все поля модели, включая унаследованные из миксинов и родительских классов.

        Алиас для get_fields() — оба используют кэш.

        Returns:
            dict[str, Field]: Словарь {имя_поля: объект_Field}

        Example:
            class AuditMixin:
                created_at = Datetime()

            class Lead(AuditMixin, DotModel):
                name = Char()

            Lead.get_all_fields()  # {'created_at': Datetime, 'name': Char, 'id': Integer}
        """
        cls._ensure_field_cache()
        return cls._cache_all_fields

    @classmethod
    def get_compute_fields(cls):
        """Только те поля, которые имеют связи. Ассоциации."""
        return [
            (name, field)
            for name, field in cls.get_fields().items()
            if field.compute
        ]

    @classmethod
    def get_relation_fields(cls):
        """Только те поля, которые имеют связи. Ассоциации."""
        return [
            (name, field)
            for name, field in cls.get_fields().items()
            if field.relation
        ]

    @classmethod
    def get_relation_fields_m2m(cls):
        """Только те поля, которые имеют связи многие ко многим."""
        return {
            name: field
            for name, field in cls.get_fields().items()
            if isinstance(field, Many2many)
        }

    @classmethod
    def get_relation_fields_m2m_o2m(cls):
        """Только те поля, которые имеют связи многие ко многим или один ко многим."""
        return [
            (name, field)
            for name, field in cls.get_fields().items()
            if isinstance(
                field, (Many2many, One2many, PolymorphicOne2many, One2one)
            )
        ]

    @classmethod
    def get_relation_fields_attachment(cls):
        """Только те поля, которые имеют связи m2o для вложений."""
        return [
            (name, field)
            for name, field in cls.get_fields().items()
            if isinstance(field, (PolymorphicMany2one, PolymorphicOne2many))
        ]

    @classmethod
    def get_store_fields(cls) -> list[str]:
        """Возвращает только те поля, которые хранятся в БД.
        Поля, у которых store = False, не хранятся в бд.
        По умолчанию все поля store = True, кроме One2many и Many2many
        """
        cls._ensure_field_cache()
        return cls._cache_store_fields

    @classmethod
    def get_store_fields_omit_m2o(cls) -> list[str]:
        """Возвращает только те поля, которые хранятся в БД.
        Поля, у которых store = False, не хранятся в бд.
        По умолчанию все поля store = True, кроме One2many и Many2many.
        Исключает m2o поля.
        Используется при чтении связанного поля, для остановки вложенности.
        """
        return [
            name
            for name, field in cls.get_fields().items()
            if field.store
            and not isinstance(field, (Many2one, PolymorphicMany2one))
        ]

    @classmethod
    def get_store_fields_dict(cls) -> dict[str, Field]:
        """Возвращает только те поля, которые хранятся в БД.
        Результат в виде dict"""
        cls._ensure_field_cache()
        return cls._cache_store_fields_dict

    @classmethod
    async def get_default_values(
        cls, fields_client_nested: dict[str, list[str]]
    ) -> dict[str, Field]:
        """
        fields_client_nested - словарь вложенных полей для полей m2m и o2m

        Возвращает поля с установленным значением по умолчанию.
        Используется при создании записи(сущности) на фронтенде. Например
        мы создаем пользователя поле active у которого по умолчанию True.
        """
        default_values = {}
        for name, field in cls.get_fields().items():
            # Для One2many и Many2many всегда возвращаем структуру x2m_default
            if isinstance(field, (One2many, Many2many)):
                fields_nested = fields_client_nested.get(name)
                if fields_nested:
                    fields_info = field.relation_table.get_fields_info_list(
                        fields_nested
                    )
                    x2m_default = {
                        "data": [],
                        "fields": fields_info,
                        "total": 0,
                    }
                    default_values.update({name: x2m_default})

            elif field.default is not None:
                if callable(field.default):
                    # если корутина то сделать авейт
                    if asyncio.iscoroutinefunction(field.default):
                        res = await field.default()
                        default_values.update({name: res})
                    # иначе просто вызов
                    else:
                        default_values.update({name: field.default()})
                else:
                    default_values.update({name: field.default})

        return default_values

    @classmethod
    def get_none_update_fields_set(cls) -> set[str]:
        """Возвращает только те поля, которые не используются при обновлении.
        1. Являются primary key (обычно id). (нельзя обновить ид)
        2. Поля, у которых store = False, не хранятся в бд.
        По умолчанию все поля store = True, кроме One2many и Many2many.
        (нельзя обновить в БД то чего там нет)
        3. Все relation поля, кроме many2one (так как это просто число, ид)
        (нельзя обновить в БД то чего там нет, one2many)
        """
        return {
            name
            for name, field in cls.get_fields().items()
            if not field.store
            or field.primary_key
            or (field.relation and not isinstance(field, Many2one))
        }

    @classmethod
    def _is_field_required(cls, field_name: str, field: Field) -> bool:
        """
        Определяет, является ли поле обязательным для API схемы.

        Приоритет:
        1. schema_required (если задан) — явное переопределение для схемы
        2. Primary key — всегда необязателен (автогенерация)
        3. required (если задан) — общая обязательность
        4. Аннотация типа — автоопределение

        Args:
            field_name: Имя поля
            field: Объект Field

        Returns:
            True если поле обязательно в схеме, False иначе
        """
        # 1. schema_required имеет высший приоритет для схемы
        if field.schema_required is not None:
            return field.schema_required

        # 2. Primary key не требует ввода от пользователя
        if field.primary_key:
            return False

        # 3. Проверяем явно заданный атрибут required
        if field.required is not None:
            return field.required

        # 3.5. Поле с default значением не обязательно в API —
        #      клиент не должен передавать то, что ORM заполнит сам.
        if field.default is not None:
            return False

        # 4. Проверяем аннотацию типа
        annotations = getattr(cls, "__annotations__", {})
        if field_name not in annotations:
            # Если аннотации нет, смотрим на null из поля
            return not field.null

        py_type = annotations[field_name]

        # Строковая аннотация: "Model | None"
        if isinstance(py_type, str):
            if "None" in py_type:
                return False
            # Проверяем на list в строке
            if py_type.startswith("list[") or py_type.startswith("List["):
                return False
            return True

        origin = get_origin(py_type)

        # Списки не обязательны (One2many, Many2many)
        if origin is list:
            return False

        # Union тип: проверяем наличие None
        if origin is UnionType or origin is Union:
            args = get_args(py_type)
            if type(None) in args:
                return False
            return True

        # Простой тип без None - обязателен
        return True

    @classmethod
    def get_fields_info_list(cls, fields_list: list[str]):
        """Get field info for list view."""
        fields_info = []
        for name, field in cls.get_fields().items():
            if name in fields_list:
                required = cls._is_field_required(name, field)
                if field.relation:
                    fields_info.append(
                        {
                            "name": name,
                            "type": field.__class__.__name__,
                            "relation": (
                                field.relation_table.__table__
                                if field.relation_table
                                else ""
                            ),
                            "required": required,
                        }
                    )
                else:
                    fields_info.append(
                        {
                            "name": name,
                            "type": field.__class__.__name__,
                            "options": field.options or [],
                            "required": required,
                        }
                    )
        return fields_info

    @classmethod
    def get_fields_info_form(cls, fields_list: list[str]):
        """Get field info for form view."""
        fields_info = []
        for name, field in cls.get_fields().items():
            if name in fields_list:
                required = cls._is_field_required(name, field)
                if field.relation:
                    fields_info.append(
                        {
                            "name": name,
                            "type": field.__class__.__name__,
                            "relatedModel": (
                                field.relation_table.__table__
                                if field.relation_table
                                else ""
                            ),
                            "relatedField": (field.relation_table_field or ""),
                            "required": required,
                        }
                    )
                else:
                    fields_info.append(
                        {
                            "name": name,
                            "type": field.__class__.__name__,
                            "options": field.options or [],
                            "required": required,
                        }
                    )
        return fields_info

    def get_json(
        self, exclude_unset=False, only_store=None, mode=JsonMode.LIST
    ):
        """Возвращает все поля модели.
        Для экземпляра класса. В экземпляре поля (класс Field)
        преобразуются в реальные данные например Integer -> int"""
        fields_json = {}
        # fields - это поля описанные в модели (классе)
        if only_store:
            fields = self.get_store_fields_dict().items()
        else:
            fields = self.get_fields().items()

        for field_name, field_class in fields:
            # field - это поле из экземпляра.
            # 1. оно может содержать данные, если задано.
            # 2. оно может содержать класс Field, если не задано.
            field = getattr(self, field_name)

            # НЕ ЗАДАНО
            # если поле экземпляра класса, осталось классом Field
            # это значит что оно не было считано из БД
            if isinstance(field, Field):
                # если установлен флаг исключить не заданные,
                # то ничего не делать
                if not exclude_unset:
                    # иначе взять значение по умолчанию или None
                    if field.default is not None:
                        # если default - callable (лямбда или функция), вызываем её
                        if callable(field.default):
                            fields_json[field_name] = field.default()
                        else:
                            fields_json[field_name] = field.default
                    else:
                        fields_json[field_name] = None

            # ЗАДАНО как many2one
            # если поле является моделью то это many2one
            elif isinstance(field, DotModel):
                if mode == JsonMode.LIST:
                    # обрубаем, исключаем все релейшен поля
                    fields_json[field_name] = {
                        "id": field.id,
                        "name": getattr(field, "name", str(field.id)),
                    }
                elif mode == JsonMode.FORM:
                    fields_json[field_name] = field.json()
                elif mode == JsonMode.CREATE or mode == JsonMode.UPDATE:
                    fields_json[field_name] = field.id

            # ЗАДАНО как many2many или one2many
            elif isinstance(
                field_class, (Many2many, One2many, PolymorphicOne2many)
            ):
                if mode == JsonMode.LIST:
                    # При search: field это list
                    fields_json[field_name] = [
                        {
                            "id": rec.id,
                            "name": rec.name or str(rec.id),
                        }
                        for rec in field
                    ]
                elif mode == JsonMode.NESTED_LIST:
                    # Вложенная сериализация оставляем как есть
                    fields_json[field_name] = field
                elif mode == JsonMode.FORM:
                    # При FORM (get) field может быть:
                    # list объектов (get с fields_nested)
                    # dict с data/fields/total (legacy)
                    if isinstance(field, dict):
                        fields_json[field_name] = {
                            "data": [
                                rec.json(mode=JsonMode.NESTED_LIST)
                                for rec in field["data"]
                            ],
                            "fields": field["fields"],
                            "total": field["total"],
                        }
                    elif isinstance(field, list):
                        fields_json[field_name] = [
                            rec.json(mode=JsonMode.NESTED_LIST)
                            for rec in field
                        ]
                    else:
                        fields_json[field_name] = field

            # Сериализуем JSONField в строку при записи в БД
            elif (
                only_store
                and isinstance(field_class, JSONField)
                and isinstance(field, (dict, list))
            ):
                fields_json[field_name] = json.dumps(field, ensure_ascii=False)
            # ЗАДАНО как значение (число строка время...)
            # иначе поле считается прочитанным из БД и просто пробрасывается
            else:
                fields_json[field_name] = field
        return fields_json

    def json(
        self,
        include={},
        exclude={},
        exclude_none=False,
        exclude_unset=False,
        only_store=None,
        mode=JsonMode.LIST,
    ):
        """Сериализация экземпляра модели в dict python.

        Keyword Arguments:
            include -- только эти поля
            exclude -- исключить поля
            exclude_none -- исключить поля со значением None
            only_store -- только те поля, которые хранятьсь в БД

        Returns:
            python dict
        """
        record = self.get_json(exclude_unset, only_store, mode)
        if include:
            record = {k: v for k, v in record.items() if k in include}
        if exclude:
            record = {k: v for k, v in record.items() if k not in exclude}
        if exclude_none:
            record = {k: v for k, v in record.items() if v is not None}
        return record

    @classmethod
    def get_onchange_fields(cls) -> list[str]:
        """
        Получить список полей у которых есть onchange обработчики.

        Используется фронтендом для определения за какими полями следить.

        Returns:
            Список имён полей с onchange обработчиками
        """
        fields_with_onchange = set()

        for attr_name in dir(cls):
            # Пропускаем dunder методы
            if attr_name.startswith("__"):
                continue
            attr = getattr(cls, attr_name, None)
            if attr and callable(attr) and hasattr(attr, "_is_onchange"):
                onchange_fields = getattr(attr, "_onchange_fields", ())
                fields_with_onchange.update(onchange_fields)

        return list(fields_with_onchange)

    @classmethod
    def _get_onchange_handlers(cls, field_name: str) -> list[str]:
        """
        Получить список методов-обработчиков для указанного поля.

        Args:
            field_name: Имя поля

        Returns:
            Список имён методов-обработчиков
        """
        handlers = []

        for attr_name in dir(cls):
            # Пропускаем dunder методы
            if attr_name.startswith("__"):
                continue
            attr = getattr(cls, attr_name, None)
            if attr and callable(attr) and hasattr(attr, "_is_onchange"):
                onchange_fields = getattr(attr, "_onchange_fields", ())
                if field_name in onchange_fields:
                    handlers.append(attr_name)

        return handlers

    async def execute_onchange(self, field_name: str) -> dict:
        """
        Выполнить все onchange обработчики для указанного поля.

        Перед вызовом self должен быть заполнен текущими значениями формы.

        Args:
            field_name: Имя изменённого поля

        Returns:
            Объединённый dict со значениями для обновления формы
        """
        result = {}
        handlers = self._get_onchange_handlers(field_name)

        for handler_name in handlers:
            handler: Awaitable | None = getattr(self, handler_name, None)
            if handler and callable(handler):
                handler_result = await handler()
                if handler_result:
                    result.update(handler_result)

        return result


# Backward compatibility alias
Model = DotModel
