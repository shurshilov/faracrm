"""ORM field definitions."""

import datetime
from decimal import Decimal as PythonDecimal
import json
import logging
from typing import TYPE_CHECKING, Any, Callable, Type, Literal

from .access import get_access_session

if TYPE_CHECKING:
    from .model import DotModel


log = logging.getLogger("dotorm")
from .exceptions import OrmConfigurationFieldException

# Допустимые значения для ondelete (общие для PostgreSQL и MySQL InnoDB)
# SET DEFAULT не поддерживается MySQL InnoDB, поэтому исключён
OnDeleteAction = Literal["restrict", "no action", "cascade", "set null"]
VALID_ONDELETE_ACTIONS = ("restrict", "no action", "cascade", "set null")


class Field[FieldType]:
    """
    Base field class.

    Attributes:
        sql_type - DB field type
        indexable - Can the field be indexed?
        store - Is the field stored in DB? (False for computed/virtual)
        required - Analog of null but reversed

        index - Create index in database?
        primary_key - Is the field primary key?
        null - Is the column nullable?
        unique - Is the field unique?
        description - Field description
        default - Default value
        options - List options for selection field
        ondelete - Foreign key ON DELETE action:
                   "restrict" - prevent deletion if referenced
                   "no action" - same as restrict (deferred in PostgreSQL)
                   "cascade" - delete child rows
                   "set null" - set foreign key to NULL

        relation - Is this a relation field?
        relation_table - Related model class
        relation_table_field - Field name in related model

        schema_required - Override required status in API schema validation
                         True = required in schema (even if nullable)
                         False = optional in schema (even if not nullable)
                         None = auto-detect from type annotation
    """

    # DB attributes
    index: bool = False
    primary_key: bool = False
    null: bool = True
    # default_orm — применять default при INSERT в Python (callable выполняется здесь).
    # default_db — применять default как DDL DEFAULT (только литералы, опт-ин).
    # default по умолчанию работает как раньше: ORM-применение включено,
    # DDL-default — нет (чтобы не менять существующие миграции).
    default_orm: bool = True
    default_db: bool = False
    unique: bool = False
    description: str | None = None
    ondelete: str = "set null"

    # ORM attributes
    required: bool | None = None
    schema_required: bool | None = None
    private: bool = False
    sql_type: str
    indexable: bool = True
    store: bool = True
    default: FieldType | None = None

    string: str = ""
    options: list[str] | None = None
    compute: Callable | None = None
    relation: bool = False
    relation_table_field: str | None = None
    _relation_table: Type["DotModel"] | None = None

    def __init__(self, **kwargs: Any) -> None:
        # schema_required - переопределяет обязательность в API схеме
        self.schema_required = kwargs.pop("schema_required", None)
        # private — исключает поле из Pydantic-схем (см. описание в классе)
        self.private = kwargs.pop("private", False)

        # Тонкий контроль того, где применяется default. По умолчанию
        # default_orm=True (как раньше — ORM подставит при INSERT),
        # default_db=False (DDL DEFAULT — осознанный опт-ин).
        self.default_orm = kwargs.pop("default_orm", self.default_orm)
        self.default_db = kwargs.pop("default_db", self.default_db)

        # добавляем поле required для удобства работы
        # которое переопределяет null
        self.required = kwargs.pop("required", None)
        if self.required is not None:
            if self.required:
                self.null = False
            else:
                self.null = True

        self.indexable = kwargs.pop("indexable", self.indexable)
        self.store = kwargs.pop("store", self.store)

        # ondelete - явное указание действия при удалении родительской записи
        # Если не указано явно, определяется автоматически на основе null
        explicit_ondelete = kwargs.pop("ondelete", None)
        if explicit_ondelete is not None:
            # Валидация допустимых значений
            if explicit_ondelete.lower() not in VALID_ONDELETE_ACTIONS:
                raise OrmConfigurationFieldException(
                    f"Invalid ondelete value: '{explicit_ondelete}'. "
                    f"Must be one of: {', '.join(VALID_ONDELETE_ACTIONS)}"
                )
            self.ondelete = explicit_ondelete.lower()
        else:
            # Автоматическое определение на основе null
            # null=True → set null (безопасно удаляет связь)
            # null=False → restrict (защищает от удаления)
            is_nullable = kwargs.get("null", self.null)
            self.ondelete = "set null" if is_nullable else "restrict"

        for name, value in kwargs.items():
            setattr(self, name, value)
        self.validation()

    # обман тайп чекера.
    def __new__(cls, *args: Any, **kwargs: Any) -> FieldType:
        return super().__new__(cls)

    def to_sql_update(self, field_name: str, value: Any) -> tuple[str, Any]:
        """Возвращает (SQL-fragment для SET-клаузы, bind-value).

        По умолчанию: 'field=%s' с обычным значением как параметром.
        Поля с особым SQL (TranslatedChar с jsonb_set, TSVector и т.п.)
        переопределяют этот метод и возвращают свой SQL-фрагмент.

        Билдер вызывает этот метод для каждого поля из payload —
        тогда никакая логика конкретных типов полей не утекает в билдер.
        """
        return f"{field_name}=%s", value

    @staticmethod
    def _can_apply_to_db(default: Any) -> bool:
        """Можно ли default сериализовать как DDL DEFAULT литерал.

        Только литералы (bool/int/float/str/bytes). Callables не идут в SQL.
        """
        if default is None or callable(default):
            return False
        return isinstance(default, (bool, int, float, str, bytes))

    @property
    def has_backend_default(self) -> bool:
        """Гарантирует ли бэк (ORM или БД) заполнение поля.

        True если default задан и хотя бы один путь применения активен:
        - default_orm=True → ORM подставит при INSERT
        - default_db=True И литерал → БД сама подставит через DDL DEFAULT
        """
        if self.default is None:
            return False
        if self.default_orm:
            return True
        if self.default_db and self._can_apply_to_db(self.default):
            return True
        return False

    def validation(self):
        if not self.indexable and (self.unique or self.index):
            raise OrmConfigurationFieldException(
                f"{self.__class__.__name__} can't be indexed"
            )

        if self.primary_key:
            # UNIQUE or PRIMARY KEY constraint to prevent duplicate values
            self.unique = True

            if self.sql_type == "INTEGER":
                self.sql_type = "SERIAL"
            elif self.sql_type == "BIGINT":
                self.sql_type = "BIGSERIAL"
            elif self.sql_type == "SMALLINT":
                self.sql_type = "SMALLSERIAL"
            else:
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} primary_key supported only for integer, bigint, smallint fields"
                )

            if not self.store:
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} primary_key required store db"
                )
            if self.null:
                log.debug(
                    f"{self.__class__.__name__} can't be both null=True and primary_key=True. Null will be ignored."
                )
                self.null = False
            if self.index:
                # self.index = False
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} can't be both index=True and primary_key=True. Primary key have index already."
                )
            # первичный ключ уже автоинкрементируется как SERIAL и имеет значение по умолчанию
            # DEFAULT nextval('tablename_colname_seq')
            if self.default:
                # self.default = None
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} can't be both default=True and primary_key=True. Primary key autoincrement already."
                )

        if self.unique:
            if self.index:
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} can't be both index=True and unique=True. Index will be ignored."
                )

    @property
    def relation_table(self):
        # если модель задана через лямбда функцию
        if (
            self._relation_table
            and not isinstance(self._relation_table, type)
            and callable(self._relation_table)
        ):
            return self._relation_table()
        # если модель задана классом
        return self._relation_table

    @relation_table.setter
    def relation_table(self, table):
        self._relation_table = table


class Integer(Field[int]):
    """Integer field (32-bit signed)."""

    field_type = int
    sql_type = "INTEGER"


class BigInteger(Field[int]):
    """Big integer field (64-bit signed)."""

    sql_type = "BIGINT"


class SmallInteger(Field[int]):
    """Small integer field (16-bit signed)."""

    sql_type = "SMALLINT"


class Char(Field[str]):
    """Character field with optional max_length."""

    field_type = str

    def __init__(self, max_length: int | None = None, **kwargs: Any) -> None:
        if max_length:
            if not isinstance(max_length, int):
                raise OrmConfigurationFieldException(
                    "'max_length' should be int, got %s" % type(max_length)
                )
            if max_length < 1:
                raise OrmConfigurationFieldException(
                    "'max_length' must be >= 1"
                )
        self.max_length = max_length
        super().__init__(**kwargs)

    @property
    def sql_type(self) -> str:
        if self.max_length:
            return f"VARCHAR({self.max_length})"
        return "VARCHAR"


class Selection(Char):
    """
    Selection field - выбор из списка опций.

    Хранится как VARCHAR, но имеет ограниченный набор допустимых значений.

    Поддерживает расширение через @extend с selection_add:

        # Базовая модель
        class ChatConnector(DotModel):
            __table__ = "chat_connector"
            type = Selection(
                options=[("internal", "Internal")],
                default="internal",
            )

        # Расширение из другого модуля
        @extend(ChatConnector)
        class ChatConnectorTelegramMixin:
            type = Selection(selection_add=[("telegram", "Telegram")])

    Args:
        options: Список кортежей (value, label) - базовые опции
        selection_add: Дополнительные опции для расширения существующего поля
        default: Значение по умолчанию
        required: Обязательное поле
    """

    def __init__(
        self,
        options: list[tuple[str, str]] | None = None,
        selection_add: list[tuple[str, str]] | None = None,
        **kwargs,
    ):
        # Базовые опции
        self._base_options: list[tuple[str, str]] = options or []
        # Опции добавленные через selection_add (из @extend)
        self._added_options: list[tuple[str, str]] = []
        # selection_add при инициализации (для @extend)
        self._selection_add = selection_add

        # Для Char нужен max_length
        if "max_length" not in kwargs:
            kwargs["max_length"] = 64

        super().__init__(**kwargs)

    @property
    def options(self) -> list[tuple[str, str]]:
        """Все опции включая добавленные через extend."""
        return self._base_options + self._added_options

    @options.setter
    def options(self, value: list[tuple[str, str]]):
        """Установить базовые опции."""
        self._base_options = value or []

    def add_options(self, new_options: list[tuple[str, str]]) -> None:
        """
        Добавить опции к полю.

        Используется системой расширений (@extend) для добавления
        новых значений в Selection поле.

        Args:
            new_options: Список кортежей (value, label)
        """
        for opt in new_options:
            if (
                opt not in self._base_options
                and opt not in self._added_options
            ):
                self._added_options.append(opt)

    def get_values(self) -> list[str]:
        """Получить список допустимых значений (без labels)."""
        return [opt[0] for opt in self.options]

    def get_label(self, value: str) -> str | None:
        """Получить label для значения."""
        for opt_value, opt_label in self.options:
            if opt_value == value:
                return opt_label
        return None

    def is_selection_add(self) -> bool:
        """Проверить является ли это расширением (selection_add)."""
        return self._selection_add is not None


class Text(Field[str]):
    """Large text field."""

    field_type = str
    indexable = False
    sql_type = "TEXT"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self.unique:
            raise OrmConfigurationFieldException(
                "TextField doesn't support unique indexes, consider CharField or another strategy"
            )
        if self.index:
            raise OrmConfigurationFieldException(
                "TextField can't be indexed, consider CharField"
            )

    class _db_mysql:
        sql_type = "LONGTEXT"


class Boolean(Field[bool]):
    """Boolean field."""

    field_type = bool
    sql_type = "BOOL"


class Decimal(Field[PythonDecimal]):
    """Accurate decimal field."""

    def __init__(
        self, max_digits: int, decimal_places: int, **kwargs: Any
    ) -> None:
        if int(max_digits) < 1:
            raise OrmConfigurationFieldException("'max_digits' must be >= 1")
        if int(decimal_places) < 0:
            raise OrmConfigurationFieldException(
                "'decimal_places' must be >= 0"
            )

        self.max_digits = int(max_digits)
        self.decimal_places = int(decimal_places)
        super().__init__(**kwargs)

    @property
    def sql_type(self) -> str:
        return f"DECIMAL({self.max_digits},{self.decimal_places})"


class Datetime(Field[datetime.datetime]):
    """Datetime field."""

    sql_type = "TIMESTAMPTZ"

    class _db_mysql:
        sql_type = "DATETIME(6)"

    class _db_postgres:
        sql_type = "TIMESTAMPTZ"


class Date(Field[datetime.date]):
    """Date field."""

    sql_type = "DATE"


class Time(Field[datetime.time]):
    """Time field."""

    sql_type = "TIME"

    class _db_mysql:
        sql_type = "TIME(6)"

    class _db_postgres:
        sql_type = "TIMETZ"


class Float(Field[float]):
    """Float (double) field."""

    sql_type = "DOUBLE PRECISION"

    class _db_mysql:
        sql_type = "DOUBLE"


class JSONField(Field[dict | list]):
    """JSON field."""

    sql_type = "JSONB"
    indexable = False

    class _db_mysql:
        sql_type = "JSON"

    def deserialization(self, value):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # Не JSON — значит это Python-input (Role(name="Admin")),
            # возвращаем как есть.
            return value
        return value

    def serialization(self, value):
        return json.dumps(value, ensure_ascii=False)

    def to_sql_update(self, field_name: str, value: Any) -> tuple[str, Any]:
        """JSONField: сериализуем dict/list в JSON-строку для BIND-параметра."""
        return f"{field_name}=%s", self.serialization(value)


class TranslatedChar(JSONField):
    """Переводимая строка.

    В БД хранится как JSONB-словарь {"en": "...", "ru": "...", ...}.
    При чтении значения для текущего языка пользователя.
    При записи строки — пишется в текущий язык, остальные переводы затираются.
    При записи dict — записывается как есть.

    Язык берётся из access_session.user_id.lang_id.code, fallback "en".
    """

    # обман тайп-чекинга на самом деле это dict | list
    # при чтении из бд, но мы всегда достаем строку
    # при этом при записи можем использовать дикты
    if TYPE_CHECKING:

        def __new__(cls, value: str = "", **kwargs: Any) -> str: ...

    else:

        def __new__(cls, *args, **kwargs):
            return super().__new__(cls)

    @staticmethod
    def _current_lang() -> str:
        """Код языка из текущей сессии.

        Контракт: session должен реализовать метод get_lang() -> str.
        Если сессии нет (фон, post_init, cron) — возвращает 'en'.
        """
        session = get_access_session()
        return session.get_lang() if session else "en"

    def deserialization(self, value):
        """JSON-строка из БД → строка для текущего языка пользователя.

        Fallback: текущий язык → 'en' → первое непустое → "".
        Если value — Python-input (Role(name="Admin")) и не JSON,
        возвращается как есть.
        """
        if not value:
            return ""

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        if not isinstance(value, dict):
            return ""

        lang = self._current_lang()
        return (
            value.get(lang)
            or value.get("en")
            or next((v for v in value.values() if v), "")
        )

    def serialization(self, value):
        """str/dict → JSON-строка для записи в БД.

        - str: оборачиваем в {current_lang: value} — используется при
          CREATE (запись новая, другим языкам взяться неоткуда).
        - dict: json.dumps как есть — multi-language override.

        При UPDATE со строкой serialization НЕ вызывается — там
        to_sql_update возвращает jsonb_set(...) для atomic merge.
        """
        if isinstance(value, str):
            value = {self._current_lang(): value}
        return super().serialization(value)

    def to_sql_update(self, field_name: str, value: Any) -> tuple[str, Any]:
        """TranslatedChar: для str — atomic jsonb_set merge в текущий язык,
        для dict — полный override через serialization (как обычный JSON).

        jsonb_set(COALESCE(col, '{}'::jsonb), '{lang}', to_jsonb(%s::text)):
        - COALESCE защищает от NULL (если колонка пустая).
        - '{lang}' — путь: обновляем только ключ текущего языка.
        - to_jsonb(%s::text) — оборачивает строку в jsonb-значение.
        Другие языки в колонке НЕ затираются — истинный merge.
        """
        if isinstance(value, str):
            lang = self._current_lang()
            sql = (
                f"{field_name} = jsonb_set("
                f"COALESCE({field_name}, '{{}}'::jsonb), "
                f"'{{{lang}}}', to_jsonb(%s::text))"
            )
            return sql, value
        return super().to_sql_update(field_name, value)


# class TranslatedText(TranslatedChar):
#     """Переводимый длинный текст. Поведение идентично TranslatedChar."""

#     pass


class Binary(Field[bytes]):
    """Binary bytes field."""

    sql_type = "BYTEA"
    indexable = False

    class _db_mysql:
        sql_type = "VARBINARY"


# ==================== RELATION FIELDS ====================


class Many2one[T: DotModel](Field[T]):
    """Many-to-one relation field."""

    field_type = Type
    sql_type = "INTEGER"
    relation = True
    relation_table: Type["DotModel"]

    def __init__(
        self, relation_table: Type["DotModel"], **kwargs: Any
    ) -> None:
        self._relation_table = relation_table
        super().__init__(**kwargs)


class PolymorphicMany2one[T: DotModel](Field[T]):
    """Many-to-one attachment field."""

    field_type = Type
    sql_type = "INTEGER"
    relation = True
    relation_table: Type["DotModel"]

    def __init__(
        self, relation_table: Type["DotModel"], **kwargs: Any
    ) -> None:
        self._relation_table = relation_table
        super().__init__(**kwargs)


class PolymorphicOne2many[T: DotModel](Field[list[T]]):
    """One-to-many attachment field."""

    field_type = list[Type]
    store = False
    relation = True
    relation_table: Type["DotModel"]
    relation_table_field: str

    def __init__(
        self,
        relation_table: Type["DotModel"],
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self._relation_table = relation_table
        self.relation_table_field = relation_table_field
        super().__init__(**kwargs)


# class Many2manyAccessor[T: "DotModel"]:
#     """
#     Accessor для работы с M2M полем на экземпляре модели.

#     Позволяет использовать удобный синтаксис:
#         await chat.member_ids.link([user1_id, user2_id])
#         await chat.member_ids.unlink([user_id])

#     Вместо:
#         await chat.link_many2many(field=Chat.member_ids, values=[[chat.id, user_id]])
#     """

#     __slots__ = ("_instance", "_field", "_data")

#     def __init__(
#         self,
#         instance: "DotModel",
#         field: "Many2many[T]",
#         data: list[T] | None = None,
#     ):
#         self._instance = instance
#         self._field = field
#         self._data = data

#     async def link(self, ids: list[int], session=None):
#         """
#         Добавить связи M2M.

#         Args:
#             ids: Список ID записей для связывания
#             session: Сессия БД

#         Example:
#             await chat.member_ids.link([user1_id, user2_id])
#         """
#         values = [[self._instance.id, id] for id in ids]
#         return await self._instance.link_many2many(
#             self._field, values, session
#         )

#     async def unlink(self, ids: list[int], session=None):
#         """
#         Удалить связи M2M.

#         Args:
#             ids: Список ID записей для отвязывания
#             session: Сессия БД

#         Example:
#             await chat.member_ids.unlink([user_id])
#         """
#         return await self._instance.unlink_many2many(self._field, ids, session)

#     # Поддержка итерации по загруженным данным
#     def __iter__(self):
#         if self._data is None:
#             return iter([])
#         return iter(self._data)

#     def __len__(self):
#         if self._data is None:
#             return 0
#         return len(self._data)

#     def __bool__(self):
#         return self._data is not None and len(self._data) > 0


class Many2many[T: DotModel](Field[list[T]]):
    """Many-to-many relation field."""

    field_type = list[Type]
    store = False
    relation = True
    relation_table: Type["DotModel"]
    many2many_table: str
    column1: str
    column2: str

    def __init__(
        self,
        relation_table: Type["DotModel"],
        many2many_table: str,
        column1: str,
        column2: str,
        **kwargs: Any,
    ) -> None:
        self.relation_table = relation_table
        self.many2many_table = many2many_table
        self.column1: str = column1
        self.column2 = column2
        super().__init__(**kwargs)

    # def __get__(
    #     self, instance: "DotModel | None", owner: type
    # ) -> "Many2many[T] | Many2manyAccessor[T]":
    #     if instance is None:
    #         # Доступ через класс — возвращаем дескриптор (для get_fields и т.д.)
    #         return self
    #     # Доступ через экземпляр — возвращаем accessor
    #     # Получаем данные если они были загружены в __dict__
    #     data = instance.__dict__.get(self._field_name)
    #     return Many2manyAccessor(instance, self, data)

    # def __set_name__(self, owner: type, name: str):
    #     self._field_name = name


class One2many[T: DotModel](Field[list[T]]):
    """One-to-many relation field."""

    field_type = list[Type]
    store = False
    relation = True
    relation_table: Type["DotModel"]
    relation_table_field: str

    def __init__(
        self,
        relation_table: Type["DotModel"],
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self._relation_table = relation_table
        self.relation_table_field = relation_table_field
        super().__init__(**kwargs)


class One2one[T: DotModel](Field[T]):
    """One-to-one relation field."""

    field_type = Type
    store = False
    relation = True
    relation_table: Type["DotModel"]

    def __init__(
        self,
        relation_table: Type["DotModel"],
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self._relation_table = relation_table
        self.relation_table_field = relation_table_field
        super().__init__(**kwargs)
