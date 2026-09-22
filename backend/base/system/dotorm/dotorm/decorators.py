"""
Декораторы для DotORM моделей - улучшенная версия.

@hybridmethod - декоратор для гибридных методов (работают И как classmethod И как instance).
@onchange - декоратор для обработчиков изменения полей.
@depends - декоратор вычисляемых (stored) полей.
@constrains - декоратор проверок записи перед INSERT/UPDATE.
@model - декоратор для бизнес-методов модели.

Эта версия улучшает типизацию через:
1. Generic типы с ParamSpec для точных параметров
2. @overload для корректной работы IDE
3. Связывание через types.MethodType — без обёртки на каждый вызов
"""

from __future__ import annotations
import functools
from types import MethodType
from typing import (
    TYPE_CHECKING,
    TypeVar,
    Generic,
    Callable,
    Any,
    Coroutine,
    overload,
    ParamSpec,
    Concatenate,
)

if TYPE_CHECKING:
    pass

# TypeVar для типизации
_T = TypeVar("_T")
_P = ParamSpec("_P")
_R = TypeVar("_R")
_R_co = TypeVar("_R_co", covariant=True)


class hybridmethod(Generic[_T, _P, _R]):
    """
    Декоратор для гибридных методов (работают И как classmethod И как instance).

    При вызове из класса (Model.method(...)) автоматически создает пустой instance.
    При вызове из instance (self.method(...)) использует существующий instance.

    Преимущества:
        - Полная обратная совместимость с существующим кодом
        - Упрощенный синтаксис в @model методах
        - self.__class__ всегда правильный класс
        - Точные типы параметров и возвращаемого значения
        - IDE автокомплит работает корректно

    Примеры использования:
        ```python
        from backend.base.system.dotorm.dotorm.decorators import hybridmethod
        from typing import Self

        class DotModel:

            @hybridmethod
            async def get(self, id: int, fields: list[str] = []) -> Self:
                '''Получить запись по ID.'''
                cls = self.__class__
                stmt, values = cls._builder.build_get(id, fields)
                record = await session.execute(stmt, values)
                return record

            @hybridmethod
            async def search(self, filter=None, **kwargs) -> list[Self]:
                '''Поиск записей.'''
                cls = self.__class__
                stmt, values = cls._builder.build_search(filter, **kwargs)
                records = await session.execute(stmt, values)
                return records

        # ✅ Вариант 1: Вызов из класса (обратная совместимость)
        user: User = await User.get(1)           # Type: User ✅
        users: list[User] = await User.search()  # Type: list[User] ✅

        # ✅ Вариант 2: Вызов из instance
        @model
        async def create_link(self, external_id: str) -> Self:
            link_id = await self.create(payload=link)  # Type: int ✅
            return await self.get(link_id)             # Type: Self ✅

        # ✅ Вариант 3: Явный пустой instance
        Model = ChatExternalChat()
        link = await Model.create_link("ext_123")
        ```

    Типизация:
        Декоратор сохраняет точные типы через:
        - Generic[_T, _P, _R] для типа класса, параметров и результата
        - ParamSpec для точных типов параметров
        - @overload для корректной работы IDE в обоих контекстах
    """

    func: Callable[..., Coroutine[Any, Any, _R]]
    __wrapped__: Callable[..., Any]
    __annotations__: dict[str, Any]
    name: str

    def __init__(
        self, func: Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]]
    ) -> None:
        self.func = func
        self.__wrapped__ = func
        functools.update_wrapper(self, func)
        self.__annotations__ = getattr(func, "__annotations__", {})
        self.name = ""

    @overload
    def __get__(
        self, instance: None, owner: type[_T]
    ) -> Callable[_P, Coroutine[Any, Any, _R]]:
        """Вызов из класса: Model.method(...)"""
        ...

    @overload
    def __get__(
        self, instance: _T, owner: type[_T]
    ) -> Callable[_P, Coroutine[Any, Any, _R]]:
        """Вызов из instance: self.method(...)"""
        ...

    def __get__(
        self, instance: _T | None, owner: type[_T]
    ) -> Callable[_P, Coroutine[Any, Any, _R]]:
        """
        Дескриптор протокол - возвращает bound метод.

        @overload позволяет IDE понимать типы в обоих случаях:
        - Model.get(1) -> IDE знает что возвращает Self
        - self.get(1) -> IDE знает что возвращает Self

        Вызов из класса (instance is None) идёт на пустом экземпляре
        owner(). Связывание — types.MethodType, а не замыкание с
        functools.wraps: __get__ срабатывает на КАЖДЫЙ вызов ORM
        (Model.search(...)), обёртка стоила 1,5 мкс и лишний слой корутины,
        MethodType — 0,2 мкс; атрибуты функции (__name__, __doc__,
        __wrapped__, __annotations__) bound method проксирует сам.

        Args:
            instance: Экземпляр класса или None (если вызов из класса)
            owner: Класс владелец

        Returns:
            Bound method с сохраненными типами параметров и результата
        """
        if instance is None:
            instance = owner()
        return MethodType(self.func, instance)

    def __set_name__(self, owner: type[Any], name: str) -> None:
        """Сохраняем имя метода для отладки."""
        self.name = name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Fallback для прямого вызова (не используется в runtime).

        Этот метод нужен для:
        1. Поддержки типизации в IDE
        2. Корректной работы inspect модуля
        """
        return self.func(*args, **kwargs)


def depends(
    *positional,
    triggers=None,
    prefetch=None,
    triggers_with_prefetch=None,
) -> Callable[[Callable], Callable]:
    """
    Декоратор для вычисляемых (stored) полей — аналог @api.depends.

    Помечает async-метод как compute-обработчик. Метод присваивает одно
    или несколько stored-полей на self. Поля связываются с методом через
    объявление ``compute="_имя_метода"`` в самом поле.

    Принимает ДВА раздельных списка:

    triggers — поля, при изменении которых метод пересчитывается:
        • локальный скаляр / M2O    → пересчёт этой же модели;
        • dotted через O2M/M2M
          ("order_line_ids.price_subtotal" / (order_line_ids, "price_subtotal"))
          → cross-model: пересчёт родителя при изменении поля ребёнка.

    prefetch — relation-поля, которые движок ДОГРУЗИТ на self ПЕРЕД
        запуском compute (чтобы читать self.tax_id.amount /
        self.order_line_ids[i].price_subtotal без fetch'ей внутри):
        • dotted M2O   ("tax_id.amount" / (tax_id, "amount"))
        • dotted O2M/M2M

    triggers_with_prefetch — шорткат: элементы попадают И в triggers,
        И в prefetch. Удобно для O2M-аггрегаций родителя, где одно и то
        же поле и триггерит, и подгружается.

    Пустой ``@depends()`` (без triggers) — метод зависит не от полей
        строки, а от всей таблицы: он пересчитывается для ВСЕХ записей
        модели после любой операции над ней (create/update/delete, bulk
        тоже). Для маленьких справочников — например, процент стадии
        воронки от максимального sequence активных стадий.

    Каждый элемент списков может быть:
        • строкой:        "price_unit", "tax_id.amount"
        • Field-объектом: price_unit, tax_id (typo ловится NameError'ом)
        • кортежем:       (tax_id, "amount") — head Field + tail-строка

    Обратная совместимость: позиционные аргументы трактуются как triggers
    (старый стиль ``@depends("a", "b")`` продолжает работать).

    Пример::

        @depends(
            triggers=[price_unit, product_uom_qty, discount, tax_id],
            prefetch=[(tax_id, "amount")],
        )
        async def _compute_amount(self): ...

        @depends(triggers_with_prefetch=[
            (order_line_ids, "price_subtotal"),
            (order_line_ids, "price_tax"),
        ])
        async def _compute_amounts(self): ...
    """

    def decorator(func: Callable) -> Callable:
        shared = list(triggers_with_prefetch or [])
        all_triggers = list(positional) + list(triggers or []) + shared
        all_prefetch = list(prefetch or []) + shared
        # Сырые элементы (Field / tuple / str). Резолв в имена-строки —
        # в _build_compute_cache, когда у Field уже проставлен .name.
        func._compute_deps_triggers = tuple(all_triggers)  # type: ignore
        func._compute_deps_prefetch = tuple(all_prefetch)  # type: ignore
        func._is_compute = True  # type: ignore[attr-defined]
        return func

    return decorator


def constrains(*fields: Any) -> Callable[[Callable], Callable]:
    """
    Декоратор проверок записи — аналог @api.constrains.

    По сути это лёгкий способ добавить ограничение сразу во все четыре
    пути записи — create, update, create_bulk, update_bulk — одной
    функцией, без override'ов каждого из них. Проверка выполняется ДО
    запроса к базе: сработала — INSERT/UPDATE не отправляется, откатывать
    нечего (см. OrmPrimaryMixin._run_constrains). Вызов один на операцию,
    как у @api.constrains с recordset: ``self`` — пустой экземпляр модели
    (как у hybridmethod от класса — для self.sudo().search(...)),
    ``records`` — записываемые payload'ы: одна запись у create/update, все
    строки у bulk; на create у записи id None, на update выставлен. Чтобы
    отклонить операцию — поднять исключение.

    Правило батчит запросы само: одно IN по значениям всех записей вместо
    запроса на строку; дубли внутри самой пачки (две новых строки с одним
    значением) в базе ещё не видны — их ловят в том же цикле. На update
    payload несёт только изменяемые поля; если нужны остальные — прочитать
    их одним search по id записей в незаданные атрибуты payload (после
    того, как правило решило, что проверка нужна). В SQL они не попадут:
    update пишет по fields, update_bulk отдаёт правилу копии.

    Аргументы — поля-триггеры (строки или Field-объекты): проверка идёт,
    когда среди записываемых полей хотя бы одной записи есть одно из них.
    Без аргументов — при любой записи модели.

    Работает и из @extend-расширений: методы собираются в кэш модели по
    маркеру, а не по имени (DotModel._build_constrains_cache), поэтому
    расширения не затирают друг друга и не требуют call_original.

    Пример::

        @constrains("login")
        async def _constrains_login_unique(self, records: list[Self]):
            by_login = {}
            for record in records:
                if not record.login:
                    continue
                if record.login in by_login:  # дубль внутри пачки
                    raise FaraException({...})
                by_login[record.login] = record
            if not by_login:
                return
            existing = await self.sudo().search(
                filter=[("login", "in", list(by_login))],
                fields=["id", "login"],
            )
            for other in existing:
                if other.id != by_login[other.login].id:  # кроме себя
                    raise FaraException({...})
    """

    def decorator(func: Callable) -> Callable:
        # Сырые элементы (str / Field) — в имена резолвит
        # _build_constrains_cache, когда у Field уже проставлен .name.
        func._constrains_fields = tuple(fields)  # type: ignore[attr-defined]
        func._is_constrains = True  # type: ignore[attr-defined]
        return func

    return decorator


# def model(
#     func: Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]],
# ) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]]:
#     """
#     Декоратор для бизнес-методов модели (фабричные методы, поиск, бизнес-логика).

#     Помечает метод как "метод уровня модели" - работает на уровне класса,
#     а не с конкретными записями. self может быть пустым экземпляром.

#     Преимущества:
#         - self.__class__ всегда правильный (с расширениями при наследовании)
#         - Instance метод - легко расширять через наследование
#         - Работает с @hybridmethod для self.get(), self.search()
#         - Правильная типизация с Self

#     Примеры использования:
#         ```python
#
#         from typing import Self

#         class ChatExternalChat(DotModel):

#             @model
#             async def create_link(
#                 self,
#                 external_id: str,
#                 connector_id: int,
#                 chat_id: int
#             ) -> Self:
#                 '''Создать связь между внешним и внутренним чатом.'''
#                 # self - пустой экземпляр
#                 # self.__class__ - ChatExternalChat (или подкласс!)

#                 link = self.__class__(
#                     external_id=external_id,
#                     connector_id=connector_id,
#                     chat_id=chat_id
#                 )

#                 # self.create(), self.get() работают благодаря @hybridmethod
#                 link_id: int = await self.create(payload=link)
#                 return await self.get(link_id)

#             @model
#             async def find_by_external_id(
#                 self,
#                 external_id: str,
#                 connector_id: int
#             ) -> Self | None:
#                 '''Найти связь по внешнему ID.'''
#                 results: list[Self] = await self.search(
#                     filter=[
#                         ("external_id", "=", external_id),
#                         ("connector_id", "=", connector_id),
#                     ],
#                     limit=1,
#                 )
#                 return results[0] if results else None

#         # Использование
#         Chat = ChatExternalChat()  # Пустой экземпляр
#         link = await Chat.create_link("ext_123", 1, 42)
#         found = await Chat.find_by_external_id("ext_123", 1)
#         ```

#     Расширение через наследование:
#         ```python
#         class TelegramChat(ChatExternalChat):

#             @model
#             async def create_link(
#                 self,
#                 external_id: str,
#                 connector_id: int,
#                 chat_id: int,
#                 thread_id: int | None = None
#             ) -> Self:
#                 '''Расширенное создание с Telegram-специфичными данными.'''
#                 # self.__class__ = TelegramChat автоматически!
#                 link = await super().create_link(external_id, connector_id, chat_id)

#                 if thread_id:
#                     link.telegram_thread_id = thread_id
#                     await link.update()

#                 return link

#         # Использование - правильный тип автоматически
#         Telegram = TelegramChat()
#         telegram_link = await Telegram.create_link("tg_123", 1, 42, thread_id=999)
#         # Type: TelegramChat ✅
#         ```
#     """

#     @functools.wraps(func)
#     async def wrapper(
#         self_or_cls: _T | type[_T], *args: _P.args, **kwargs: _P.kwargs
#     ) -> _R:
#         # Поддержка вызова и из класса и из instance
#         if isinstance(self_or_cls, type):
#             # Вызов из класса: ChatExternalChat.create_link(...)
#             instance: _T = self_or_cls()
#         else:
#             # Вызов из instance: chat.create_link(...)
#             instance = self_or_cls

#         return await func(instance, *args, **kwargs)

#     # Помечаем метод специальным атрибутом для introspection
#     wrapper._dotorm_model_method = True  # type: ignore[attr-defined]
#     wrapper._original_func = func  # type: ignore[attr-defined]

#     return wrapper


# Экспортируем декораторы
__all__ = ["hybridmethod", "onchange", "depends", "constrains"]


def onchange(*fields: str):
    """
    Декоратор для регистрации обработчиков изменения полей.

    При изменении указанных полей на фронтенде
    вызывается декорированный метод, который может вернуть значения для
    обновления других полей формы.

    Примеры использования:
        ```python
        from backend.base.system.dotorm.dotorm.decorators import onchange

        class ChatConnector(DotModel):

            @onchange('type')
            async def _onchange_type(self) -> dict:
                '''Вызывается при изменении поля type'''
                if self.type == 'telegram':
                    return {
                        'connector_url': 'https://api.telegram.org',
                        'category': 'messenger',
                    }
                return {}

            @onchange('category', 'type')
            async def _onchange_category_type(self) -> dict:
                '''Вызывается при изменении category или type'''
                # self содержит текущие значения формы
                return {'name': f'{self.category} - {self.type}'}
        ```

    Поведение:
        - Метод должен быть async
        - self заполняется текущими значениями формы
        - Метод возвращает dict с полями для обновления
        - Пустой dict {} означает "ничего не менять"
        - Цепочки onchange НЕ поддерживаются (если onchange меняет поле
          у которого тоже есть onchange, второй НЕ вызывается)

    Args:
        *fields: Имена полей, при изменении которых вызывать обработчик

    Returns:
        Декоратор функции
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, dict]]):
        # Помечаем функцию как onchange обработчик
        func._onchange_fields = fields
        func._is_onchange = True

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs) -> dict:
            result = await func(self, *args, **kwargs)
            # Гарантируем что результат - словарь
            if result is None:
                return {}
            return result

        # Переносим метаданные на wrapper
        wrapper._onchange_fields = fields  # type: ignore
        wrapper._is_onchange = True  # type: ignore

        return wrapper

    return decorator
