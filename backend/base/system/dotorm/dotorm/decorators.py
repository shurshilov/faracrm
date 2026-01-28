"""
Декораторы для DotORM моделей - улучшенная версия.

@hybridmethod - декоратор для гибридных методов (работают И как classmethod И как instance).
@onchange - декоратор для обработчиков изменения полей.
@model - декоратор для бизнес-методов модели.

Эта версия улучшает типизацию через:
1. Generic типы с ParamSpec для точных параметров
2. @overload для корректной работы IDE
3. __slots__ для производительности
"""

from __future__ import annotations
import functools
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

    __slots__ = ("func", "__wrapped__", "name", "__dict__")

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

        Args:
            instance: Экземпляр класса или None (если вызов из класса)
            owner: Класс владелец

        Returns:
            Async функция с сохраненными типами параметров и результата
        """
        if instance is None:
            # Вызов из класса: Model.method(...)
            # Автоматически создаем пустой instance
            @functools.wraps(self.func)
            async def class_method(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                empty_instance = owner()
                return await self.func(empty_instance, *args, **kwargs)

            class_method.__annotations__ = self.__annotations__
            return class_method
        else:
            # Вызов из instance: self.method(...)
            # Используем существующий instance
            @functools.wraps(self.func)
            async def instance_method(
                *args: _P.args, **kwargs: _P.kwargs
            ) -> _R:
                return await self.func(instance, *args, **kwargs)

            instance_method.__annotations__ = self.__annotations__
            return instance_method

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


def depends(*field_names: str) -> Callable[[Callable], Callable]:
    """
    Декоратор для вычисляемых полей.
    Указывает, от каких полей зависит вычисление.
    Поддерживает вложенные зависимости.
    """

    def decorator(func: Callable) -> Callable:
        func.compute_deps = set(field_names)
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
__all__ = ["hybridmethod", "onchange"]


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
