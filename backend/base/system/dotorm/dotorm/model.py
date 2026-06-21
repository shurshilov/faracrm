"""DotModel - main ORM model class."""

from abc import ABCMeta
import asyncio
from enum import IntEnum
from types import UnionType
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
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
    TranslatedChar,
)


class JsonMode(IntEnum):
    """Modes for JSON serialization of model instances."""

    FORM = 1
    LIST = 2
    CREATE = 3
    UPDATE = 4
    NESTED_LIST = 5  # Для вложенных записей внутри FORM


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class ModelMetaclass(ABCMeta):
    """Metaclass for DotModel with dataclass_transform support."""


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
    # Составные индексы таблицы. Список кортежей имён колонок.
    # Пример: __indexes__ = [("res_model", "res_id"), ("user_id", "chat_id", "is_active")]
    # Одиночные индексы по-прежнему объявляются через index=True в поле.
    # Имя индекса генерируется автоматически: idx_<table>_<col1>_<col2>_...
    # Создаётся через CREATE INDEX IF NOT EXISTS, так что безопасно при повторном запуске.
    __indexes__: ClassVar[list[tuple[str, ...]]] = []
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

        # Build field cache eagerly — runs once per class definition.
        # Each subclass (Lead, Activity, etc.) sees full MRO including mixins.
        cls._build_field_cache()
        # @depends compute cache. Должен идти ПОСЛЕ _build_field_cache,
        # потому что использует _cache_all_fields для определения, какие
        # поля пишет каждый compute-метод (через field.compute=...).
        cls._build_compute_cache()

    @classmethod
    def _build_field_cache(cls):
        """Build all field caches from MRO. Called once in __init_subclass__."""
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
        cls._cache_relation_fields = [
            (name, field) for name, field in fields.items() if field.relation
        ]
        json_fields = [
            name
            for name, field in fields.items()
            if isinstance(field, (JSONField, TranslatedChar))
        ]
        compute_fields = [
            (name, field)
            for name, field in fields.items()
            if field.compute and not field.store
        ]
        cls._cache_json_fields = json_fields
        cls._cache_compute_fields = compute_fields
        cls._cache_has_json_fields = bool(json_fields)
        cls._cache_has_compute_fields = bool(compute_fields)

    @classmethod
    def _build_compute_cache(cls):
        """Собрать @depends-методы для движка _collect_depends + recompute().

        Заполняет per-class:
        - _cache_compute_method_deps: {method → tuple(deps)} —
          вход для OrmPrimaryMixin._build_depends_tables (строит
          _depends_local_triggers / _depends_parent_triggers).
        - _cache_compute_writes: {method → set(written_fields)} —
          OrmPrimaryMixin._fire_compute персистит эти поля и каскадирует.
        - _cache_compute_by_dep: {dep_local_segment → set(methods)} —
          вход для recompute() (in-memory путь, см. execute_onchange).
        - _cache_compute_order: list[method_name] — порядок объявления,
          без топосорта. Каскад через _collect_depends на written-полях
          сам подтягивает downstream-методы — отдельная сортировка не
          нужна.
        - _cache_has_compute_methods: bool.

        Вызывается один раз из __init_subclass__ после _build_field_cache.
        """

        # Резолвер: превращает любой допустимый формат dep в строку имени.
        # Поддерживает:
        #   "price_unit"            → "price_unit"
        #   "tax_id.amount"         → "tax_id.amount"
        #   tax_id (Field-инстанс)  → "tax_id"  (из field.name, заданного __set_name__)
        #   (tax_id, "amount")      → "tax_id.amount"
        # Field-инстансы в class-attr scope @depends — это сам объект
        # (Field.__get__ возвращает self при class-level access). Их name
        # уже проставлен Python через __set_name__ при создании класса.
        def _resolve_dep(d) -> str | None:
            if isinstance(d, str):
                return d
            if isinstance(d, Field):
                return d.name or None
            if isinstance(d, tuple) and len(d) == 2:
                head, tail = d
                head_name = head.name if isinstance(head, Field) else head
                if isinstance(head_name, str) and isinstance(tail, str):
                    return f"{head_name}.{tail}"
            return None

        def _resolve_list(raw) -> tuple[str, ...]:
            return tuple(d for d in (_resolve_dep(x) for x in raw) if d)

        # Два раздельных списка на метод:
        #   triggers — поля, при изменении которых метод пересчитывается;
        #   prefetch — relation-пути, которые догружаются перед compute.
        method_deps: dict[str, tuple[str, ...]] = {}
        method_prefetch: dict[str, tuple[str, ...]] = {}
        for klass in reversed(cls.__mro__):
            if klass is object:
                continue
            for attr_name, attr in klass.__dict__.items():
                func = getattr(attr, "__func__", attr)
                if callable(func) and getattr(func, "_is_compute", False):
                    method_deps[attr_name] = _resolve_list(
                        getattr(func, "_compute_deps_triggers", ())
                    )
                    method_prefetch[attr_name] = _resolve_list(
                        getattr(func, "_compute_deps_prefetch", ())
                    )

        # имя_метода → множество полей, которые он пишет
        # (определяется по объявлению compute="..." / compute=callable
        # в самих полях; собирается из _cache_all_fields).
        method_writes: dict[str, set[str]] = {m: set() for m in method_deps}
        for fname, field in cls._cache_all_fields.items():
            comp = field.compute
            if isinstance(comp, str):
                target = comp
            elif callable(comp):
                target = getattr(comp, "__name__", None)
            else:
                target = None
            if target in method_writes:
                method_writes[target].add(fname)

        # dep-поле (локальный первый сегмент пути) → методы.
        # Только из triggers (prefetch — это про загрузку, не про
        # инвалидацию). Нужно recompute()/onchange: по триггерному полю
        # формы выбираются методы, чьи triggers его упоминают.
        by_dep: dict[str, set[str]] = {}
        for m, deps in method_deps.items():
            for d in deps:
                local = d.split(".", 1)[0]
                by_dep.setdefault(local, set()).add(m)

        cls._cache_compute_method_deps = method_deps
        cls._cache_compute_prefetch_deps = method_prefetch
        cls._cache_compute_writes = method_writes
        cls._cache_compute_by_dep = by_dep
        cls._cache_compute_order = list(method_deps.keys())
        cls._cache_has_compute_methods = bool(method_deps)

    async def recompute(
        self, changed: set[str] | None = None, session=None
    ) -> set[str]:
        """In-memory пересчёт stored computed-полей @depends на self.

        Используется ИСКЛЮЧИТЕЛЬНО из execute_onchange — там нужно
        пересчитать поля для возврата на форму, не записывая в БД.
        В CRUD-пути работает _collect_depends (он же персистит результат
        и поднимает родителей через _depends_parent_triggers).

        Args:
            changed: если задано — запускаются только методы, чьи
                зависимости пересекаются с этими полями (по локальному
                первому сегменту пути). None — все методы.

        Returns:
            Множество имён полей, перезаписанных пересчётом.
        """
        cls = self.__class__
        if not cls._cache_has_compute_methods:
            return set()

        order = cls._cache_compute_order
        if changed is None:
            methods = list(order)
        else:
            triggered: set[str] = set()
            for f in changed:
                triggered |= cls._cache_compute_by_dep.get(f, set())
            if not triggered:
                return set()
            methods = [m for m in order if m in triggered]

        written: set[str] = set()
        for mname in methods:
            handler = getattr(self, mname, None)
            if handler is None:
                continue
            # Догружаем relation-поля, объявленные в dotted @depends
            # этого метода — тот же контракт, что в _fire_compute из
            # CRUD-пути. Compute читает self.tax_id.amount и
            # self.order_line_ids[i].price_subtotal без fetch'ей внутри.
            await self._ensure_prefetch_for_method(mname, session)
            result = handler()
            if asyncio.iscoroutine(result):
                await result
            written |= cls._cache_compute_writes.get(mname, set())
        return written

    def __init__(self, **kwargs: Any) -> None:
        # Fast path: bulk-assign all kwargs via __dict__
        self.__dict__.update(kwargs)

        cls = self.__class__

        # Десериализация JSON полей (если пришла строка из БД)
        # asyncpg не десериализует jsonb автоматически без кодека,
        # поэтому нужен fallback json.loads для строковых значений.
        # Для TranslatedChar дополнительно распаковываем dict в строку
        # текущего языка пользователя.
        if cls._cache_has_json_fields:
            cls_fields = cls._cache_all_fields
            for name in cls._cache_json_fields:
                value = self.__dict__.get(name)
                if value is not None:
                    self.__dict__[name] = cls_fields[name].deserialization(
                        value
                    )
            # cls_fields = cls._cache_all_fields
            # for name in cls._cache_json_fields:
            #     value = self.__dict__.get(name)
            #     if isinstance(value, str):
            #         field_obj = cls_fields.get(name)
            #         if field_obj:
            #             self.__dict__[name] = field_obj.deserialization(value)

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
            raise ValueError("More than 1 record in form")
        record = cls(**r[0])
        return record

    @classmethod
    def prepare_list_ids(cls, rows: list):
        """Десериализация из списка записей (dict или asyncpg Record) в список объектов.

        Fast path: bypasses __init__ when model has no JSON/compute fields.
        Uses object.__new__ + __dict__.update — same approach as SQLAlchemy.
        """
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
            raise ValueError(f"Expected exactly 1 record, got {len(r)}")
        record = cls(**r[0])
        return record

    @classmethod
    def get_fields(cls) -> dict[str, Field]:
        """Возвращает все поля модели, включая унаследованные из миксинов.

        Использует кэш для избежания MRO traversal на каждом вызове.
        """
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
        """Только те поля, которые имеют связи. Ассоциации. Кешируется."""
        return cls._cache_relation_fields

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
        return cls._cache_store_fields_dict

    def is_assigned(self, name: str) -> bool:
        """True если поле было явно присвоено на этом инстансе.

        Источник правды — `instance.__dict__`: Python пишет туда при
        обычном setattr (Field — non-data descriptor, без __set__).

        Случаи:
          rec.tax_id = 5      → is_assigned("tax_id") = True
          rec.tax_id = None   → is_assigned("tax_id") = True (явный None)
          никогда не задавали → is_assigned("tax_id") = False

        Используется в местах, где нужно отличать «явно None» от
        «не загружено» (apply_defaults, json exclude_unset, и т.п.).
        Когда такого различия не нужно — просто читай `rec.tax_id`,
        он сам вернёт None при не-назначенном поле через Field.__get__.
        """
        return name in self.__dict__

    def assigned_fields(
        self,
        exclude: tuple[str, ...] = ("id",),
        exclude_none: bool = False,
    ) -> list[str]:
        """Список имён полей, которые явно присвоены на этом инстансе.

        Используется для:
          - автоопределения `fields=` в update без явного списка;
          - построения списка изменённых полей для `_collect_depends`
            в delete / delete_bulk / create / create_bulk.

        Args:
            exclude: не включать поля с этими именами (по умолчанию "id").
            exclude_none: если True, поля со значением `None` тоже
                пропустить. По умолчанию False: `payload.tax_id = None`
                — это валидное явное значение «обнулить FK», и compute,
                подписанный на tax_id, должен это увидеть.
        """

        instance_dict = self.__dict__
        return [
            # проходим все поля в классе
            name
            for name in self._cache_all_fields
            if name not in exclude
            and name in instance_dict
            and not (exclude_none and instance_dict[name] is None)
        ]

    @classmethod
    async def get_default_values(
        cls, fields_client_nested: dict[str, list[str]]
    ):
        default_values = {}

        for name, field in cls.get_fields().items():
            is_x2m = isinstance(field, (One2many, Many2many))

            # 1. Получаем само значение (разрешаем callable и async)
            value = field.default
            if callable(value):
                value = (
                    await value()
                    if asyncio.iscoroutinefunction(value)
                    else value()
                )

            # 2. Обработка x2m полей (подготовка структуры)
            if is_x2m:
                nested_names = fields_client_nested.get(name)
                # Если есть вложенные поля, создаем спец. структуру, иначе пропускаем
                if nested_names:
                    if value:
                        data = [value_item.json_list() for value_item in value]
                    else:
                        data = []
                    default_values[name] = {
                        "data": data,
                        "fields": field.relation_table.get_fields_info_list(
                            nested_names
                        ),
                        "total": len(data),
                    }
            elif isinstance(field, Many2one) and isinstance(value, DotModel):
                default_values[name] = value.json(mode=JsonMode.FORM)
            # 3. Обработка обычных полей
            elif value is not None:
                default_values[name] = value

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

        # 3.5. Поле с гарантированным backend-default'ом не обязательно
        #      в API — клиент не должен передавать то, что бэк подставит сам.
        #      Учитываются default_orm и default_db (см. fields.Field).
        if field.has_backend_default:
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
        self,
        exclude_unset=False,
        only_store=None,
        mode=JsonMode.LIST,
        include=None,
        exclude=None,
    ):
        """Возвращает все поля модели.
        Для экземпляра класса. В экземпляре поля (класс Field)
        преобразуются в реальные данные например Integer -> int

        Args:
            include: если задан — обрабатывать ТОЛЬКО эти поля.
                     Остальные пропускаются ДО вычисления дефолтов,
                     что предотвращает побочные эффекты для несчитанных полей.
            exclude: если задан — пропускать эти поля.
        """
        fields_json = {}
        # fields - это поля описанные в модели (классе)
        if only_store:
            fields = self.get_store_fields_dict().items()
        else:
            fields = self.get_fields().items()

        for field_name, field_class in fields:
            # Раннее отсечение: если задан include/exclude,
            # пропускаем поле ДО любых вычислений (дефолты, рекурсия)
            if include and field_name not in include:
                continue
            if exclude and field_name in exclude:
                continue

            # НЕ ЗАДАНО
            # Поле не присвоено на этом инстансе (отсутствует в __dict__).
            # Сериализация не вычисляет default (это задача create).
            # exclude_unset=True → пропускаем (как Pydantic).
            # exclude_unset=False → ставим None чтобы ключ был в dict.
            if not self.is_assigned(field_name):
                if not exclude_unset:
                    fields_json[field_name] = None
                continue

            # ЗАДАНО — значение либо реальное, либо явный None.
            field = getattr(self, field_name)

            # ЗАДАНО как many2one
            # если поле является моделью то это many2one
            if isinstance(field, DotModel):
                if mode == JsonMode.LIST:
                    # обрубаем, исключаем все релейшен поля
                    fields_json[field_name] = field.json_list()
                elif mode == JsonMode.NESTED_LIST:
                    # Вложенный список (напр. O2M внутри FORM) —
                    # для Many2one также возвращаем компактное {id, name},
                    # иначе поле теряется при сериализации.
                    fields_json[field_name] = field.json_list()
                elif mode == JsonMode.FORM:
                    fields_json[field_name] = field.json(
                        exclude_unset=True, mode=JsonMode.FORM
                    )
                elif mode in (JsonMode.CREATE, JsonMode.UPDATE):
                    fields_json[field_name] = field.id

            # ЗАДАНО как int/id для Many2one (FK не развёрнут в объект)
            elif isinstance(field, (int,)) and isinstance(
                field_class, (Many2one, PolymorphicMany2one)
            ):
                if mode in (JsonMode.CREATE, JsonMode.UPDATE):
                    fields_json[field_name] = field
                else:
                    fields_json[field_name] = {
                        "id": field,
                        "name": str(field),
                    }

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
                                rec.json(
                                    mode=JsonMode.NESTED_LIST,
                                    exclude_unset=True,
                                )
                                for rec in field["data"]
                            ],
                            "fields": field["fields"],
                            "total": field["total"],
                        }
                    elif isinstance(field, list):
                        fields_json[field_name] = [
                            rec.json(
                                mode=JsonMode.NESTED_LIST,
                                exclude_unset=True,
                            )
                            for rec in field
                        ]
                    else:
                        fields_json[field_name] = field

            # JSONField / TranslatedChar при записи в БД.
            # При UPDATE оставляем сырое значение — билдер через
            # field.to_sql_update сам построит SET-клаузу:
            # для TranslatedChar+str → jsonb_set (atomic merge в язык),
            # для dict/list → обычный %s с json.dumps.
            # При CREATE сериализуем сразу в JSON-строку (через %s в INSERT).
            elif only_store and isinstance(
                field_class, (JSONField, TranslatedChar)
            ):
                if mode == JsonMode.UPDATE:
                    fields_json[field_name] = field
                else:
                    fields_json[field_name] = field_class.serialization(field)
            # ЗАДАНО как значение (число строка время...)
            # иначе поле считается прочитанным из БД и просто пробрасывается
            else:
                fields_json[field_name] = field
        return fields_json

    def json_list(self):
        """Сериализация для LIST mode (вложенный M2O).

        По умолчанию возвращает {id, name}.
        Модели могут переопределить для добавления полей.
        """
        return {
            "id": self.id,
            "name": getattr(self, "name", str(self.id)),
        }
        # fields = {"id": self.id}
        # if getattr(self, "name"):
        #     fields.update({"name": self.name})
        # return fields

    def json(
        self,
        include=None,
        exclude=None,
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
        record = self.get_json(
            exclude_unset, only_store, mode, include=include, exclude=exclude
        )
        if exclude_none:
            record = {k: v for k, v in record.items() if v is not None}
        return record

    @classmethod
    def get_onchange_fields(cls) -> list[str]:
        """
        Получить список полей у которых есть onchange обработчики.

        Возвращает объединение:
          - полей с явным @onchange-декоратором;
          - полей-триггеров из @depends (через _cache_compute_by_dep.keys()).
            Фронт должен следить и за ними, чтобы при изменении price_unit
            автоматически шёл /onchange и приходили пересчитанные
            price_subtotal / price_tax / price_total и т.д.

        Используется фронтендом для определения за какими полями следить.
        """
        fields_with_onchange = set()

        for attr_name in dir(cls):
            if attr_name.startswith("__"):
                continue
            attr = getattr(cls, attr_name, None)
            if attr and callable(attr) and hasattr(attr, "_is_onchange"):
                onchange_fields = getattr(attr, "_onchange_fields", ())
                fields_with_onchange.update(onchange_fields)

        # Поля-триггеры всех @depends-методов модели — фронту нужно
        # дёрнуть /onchange при их изменении, чтобы получить свежие
        # значения computed-полей (price_subtotal и т.д.).
        fields_with_onchange.update(cls._cache_compute_by_dep.keys())

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
        Выполнить onchange обработчики для указанного поля.

        Делает ДВА прохода:
          1. Явные @onchange-handlers — для пользовательской логики
             ("при выборе product подставить product_uom_id").
          2. Recompute @depends-методов, чьи триггеры содержат field_name —
             через тот же движок, что и в CRUD-пути. Compute читает
             self.tax_id.amount / self.order_line_ids и т.п. через
             _ensure_prefetch_for_method.

        Перед вызовом self должен быть заполнен текущими значениями формы.

        Returns:
            Объединённый dict со значениями для обновления формы.
            Включает и поля изменённые @onchange-handler'ами, и
            пересчитанные @depends computed-поля (price_subtotal и т.п.).
        """
        result: dict = {}

        # 1. @onchange handlers — кастомная логика пользователя.
        for handler_name in self._get_onchange_handlers(field_name):
            handler: Awaitable | None = getattr(self, handler_name, None)
            if handler and callable(handler):
                handler_result = await handler()
                if handler_result:
                    result.update(handler_result)

        # 2. @depends recompute — пересчёт computed-полей по триггеру.
        cls = self.__class__
        if cls._cache_has_compute_methods:
            written = await self.recompute(changed={field_name})
            for name in written:
                value = getattr(self, name, None)
                # Под non-data Field-descriptor (Variant C) getattr на
                # non-assigned поле уже возвращает None, а не Field.
                # Безопасно включаем любое значение, кроме явно
                # ничего-не-делающего None.
                if value is not None:
                    result[name] = value

        return result


# Backward compatibility alias
Model = DotModel
