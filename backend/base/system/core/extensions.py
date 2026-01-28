"""
Система расширения моделей для Fara CRM.

Используйте @extend(Model) когда нужно добавить поля/методы к существующей модели
БЕЗ изменения её исходного кода.

Для переиспользуемой функциональности (миксины) используйте стандартное
наследование Python:

    class AuditMixin:
        created_at = Datetime()
        updated_at = Datetime()

    class Lead(AuditMixin, DotModel):
        __table__ = "lead"
        name = Char()

Пример @extend:

    from backend.base.crm.leads.models.leads import Lead

    @extend(Lead)
    class LeadExtension:
        priority = Integer()
        source = Char()

        def calculate_score(self) -> int:
            return self.priority * 10
"""

from typing import (
    Type,
    Dict,
    List,
    Set,
    Any,
    Callable,
    Optional,
    Union,
    TypeVar,
)
from functools import wraps
import logging

log = logging.getLogger(__name__)

T = TypeVar("T")


def _get_model_key(target: Union[Type, str]) -> str:
    """
    Получить ключ модели (имя таблицы) из класса или строки.

    Args:
        target: Класс модели или строка с именем таблицы

    Returns:
        Имя таблицы (__table__)
    """
    if isinstance(target, str):
        return target
    elif isinstance(target, type):
        table = getattr(target, "__table__", None)
        if table is None:
            raise ValueError(
                f"Class {target.__name__} does not have __table__ attribute. "
                f"Make sure it inherits from DotModel."
            )
        return table
    else:
        raise TypeError(
            f"Expected model class or string, got {type(target).__name__}"
        )


def _get_model_name(target: Union[Type, str]) -> str:
    """Получить человекочитаемое имя модели для логов."""
    if isinstance(target, str):
        return f"'{target}'"
    elif isinstance(target, type):
        return target.__name__
    return str(target)


class ExtensionRegistry:
    """
    Реестр расширений моделей.

    Хранит расширения (@extend) и применяет их к моделям при первом доступе.
    """

    _instance: Optional["ExtensionRegistry"] = None

    def __new__(cls) -> "ExtensionRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_registry()
        return cls._instance

    def _init_registry(self):
        """Инициализация внутренних структур."""
        self._extensions: Dict[str, List[Dict[str, Any]]] = {}
        self._applied: Set[str] = set()
        self._original_methods: Dict[str, Dict[str, Callable]] = {}

    def add_extension(
        self, target: Union[Type, str], namespace: Dict[str, Any]
    ) -> None:
        """
        Добавить расширение для модели.

        Args:
            target: Класс модели или имя таблицы
            namespace: Словарь с атрибутами расширения (поля и методы)
        """
        table_name = _get_model_key(target)

        if table_name not in self._extensions:
            self._extensions[table_name] = []
        self._extensions[table_name].append(namespace)

        log.info(f"Registered extension for {_get_model_name(target)}")

    def apply_to_model(self, model_class: Type) -> Type:
        """
        Применить все расширения к модели.

        Args:
            model_class: Класс модели для расширения

        Returns:
            Тот же класс модели с добавленными полями/методами
        """
        table_name = getattr(model_class, "__table__", None)
        if not table_name:
            return model_class

        # Не применяем повторно
        if table_name in self._applied:
            return model_class

        extensions = self._extensions.get(table_name, [])
        if not extensions:
            self._applied.add(table_name)
            return model_class

        log.debug(
            f"Applying {len(extensions)} extension(s) to {model_class.__name__}"
        )

        for ext in extensions:
            self._apply_extension(model_class, ext)

        self._applied.add(table_name)
        log.info(f"Extensions applied to {model_class.__name__}")

        return model_class

    def _apply_extension(self, model: Type, namespace: Dict[str, Any]) -> None:
        """Применить namespace расширения к модели."""
        from backend.base.system.dotorm.dotorm.fields import Field, Selection

        for name, value in namespace.items():
            if name.startswith("_"):
                continue

            if isinstance(value, Field):
                # Проверяем: это Selection с selection_add?
                if isinstance(value, Selection) and value.is_selection_add():
                    # Расширяем существующее Selection поле
                    existing_field = getattr(model, name, None)
                    if existing_field and isinstance(
                        existing_field, Selection
                    ):
                        existing_field.add_options(value._selection_add)
                        log.debug(
                            f"  + selection_add '{name}': {value._selection_add}"
                        )
                    else:
                        log.warning(
                            f"  ! Cannot apply selection_add to '{name}': "
                            f"field not found or not Selection"
                        )
                else:
                    # Обычное поле - добавляем/заменяем
                    setattr(model, name, value)
                    log.debug(f"  + field '{name}'")

            elif callable(value) and not isinstance(value, type):
                # Добавляем/переопределяем метод
                self._apply_method(model, name, value)

            elif name.isupper():
                # Константы (UPPER_CASE) - копируем как есть
                setattr(model, name, value)
                # log.debug(f"  + constant '{name}'")

    def _apply_method(
        self, model: Type, name: str, new_method: Callable
    ) -> None:
        """Применить метод к модели с сохранением оригинала."""
        original = getattr(model, name, None)
        table_name = model.__table__

        # Сохраняем оригинальный метод для возможности вызова через call_original()
        if original and callable(original):
            if table_name not in self._original_methods:
                self._original_methods[table_name] = {}
            if name not in self._original_methods[table_name]:
                self._original_methods[table_name][name] = original

        # Устанавливаем новый метод
        setattr(model, name, new_method)
        log.debug(f"  + method '{name}'")

    def get_original_method(
        self, model: Union[Type, str], method_name: str
    ) -> Optional[Callable]:
        """
        Получить оригинальный метод модели (до применения расширений).

        Используется для вызова родительской реализации из расширения.
        """
        table_name = _get_model_key(model)
        return self._original_methods.get(table_name, {}).get(method_name)

    def is_applied(self, model: Union[Type, str]) -> bool:
        """Проверить, применены ли расширения к модели."""
        table_name = _get_model_key(model)
        return table_name in self._applied

    def clear(self) -> None:
        """Очистить реестр (для тестов)."""
        self._init_registry()
        log.info("Extension registry cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику расширений."""
        return {
            "extensions_count": sum(len(v) for v in self._extensions.values()),
            "applied_models": list(self._applied),
            "models_with_extensions": list(self._extensions.keys()),
        }


# Глобальный экземпляр реестра
registry = ExtensionRegistry()


# ============== ДЕКОРАТОР @extend ==============

M = TypeVar("M")  # Mixin class


def extend(target: Union[Type[T], str]) -> Callable[[Type[M]], Type[M]]:
    """
    Декоратор для расширения существующей модели.

    Добавляет поля и методы к модели БЕЗ создания нового класса.
    Это позволяет расширять модели из базового пакета без изменения их кода.

    Args:
        target: Класс модели или имя таблицы (__table__)

    Returns:
        Декоратор, который возвращает класс расширения с сохранением его типа.
        Это позволяет IDE видеть все поля и методы mixin класса.

    Примеры:
        # Рекомендуемый способ - передача класса (type-safe):
        from backend.base.crm.leads.models.leads import Lead

        @extend(Lead)
        class LeadExtension:
            priority: int = Integer(default=0)
            source: str = Char()

            def is_high_priority(self) -> bool:
                return self.priority > 5

        # Альтернатива - строка (если есть циклические импорты):
        @extend('lead')
        class LeadExtension:
            priority: int = Integer(default=0)

    Note:
        Для переиспользуемых миксинов используйте стандартное наследование:

        class AuditMixin:
            created_at = Datetime()

        class MyModel(AuditMixin, DotModel):
            ...
    """

    def decorator(extension_class: Type[M]) -> Type[M]:
        # Собираем все атрибуты кроме dunder
        namespace = {
            name: value
            for name, value in extension_class.__dict__.items()
            if not name.startswith("__")
        }

        # Регистрируем расширение
        registry.add_extension(target, namespace)

        # Сохраняем информацию о целевой модели
        extension_class._extends = target  # type: ignore

        return extension_class

    return decorator


# ============== EXTENSIBLE MIXIN ==============


class ExtensibleMixin:
    """
    Миксин для добавления поддержки расширений (@extend) к ModelsCore.

    Автоматически:
    1. Ищет и загружает расширения из пакетов в _autodiscover
    2. Применяет @extend расширения при первом доступе к модели

    Attributes:
        _autodiscover: Список пакетов для поиска расширений (*_ext.py, extensions/)

    Example:
        from backend.base.system.core.models import ModelsCore
        from backend.base.system.core.extensions import ExtensibleMixin

        class Models(ExtensibleMixin, ModelsCore):
            # Можно переопределить пакеты для поиска
            _autodiscover = ['backend.business', 'myapp.extensions']

            lead = Lead
            partner = Partner
    """

    # Пакеты по умолчанию для поиска расширений
    _autodiscover: List[str] = [
        "backend.business",
        "backend.base.crm",
        "backend.base.system",
    ]

    _autodiscover_done: bool = False

    def __init__(self):
        object.__setattr__(self, "_cache", {})
        self._run_autodiscover()
        # Вызываем __init__ родителя если есть
        super().__init__()

    @classmethod
    def _run_autodiscover(cls):
        """Автоматический поиск и загрузка расширений."""
        if cls._autodiscover_done:
            return

        packages = cls._autodiscover
        if not packages:
            cls._autodiscover_done = True
            return

        import importlib
        import pkgutil
        from pathlib import Path

        loaded = 0

        for package_path in packages:
            try:
                package = importlib.import_module(package_path)
            except ImportError as e:
                log.debug(f"Package {package_path} not found, skipping: {e}")
                continue

            # Получаем директорию пакета
            # __file__ может быть None для namespace packages
            if hasattr(package, "__file__") and package.__file__:
                package_dir = Path(package.__file__).parent
                search_paths = [str(package_dir)]
            elif hasattr(package, "__path__"):
                # Namespace package - используем __path__
                search_paths = list(package.__path__)
            else:
                log.debug(
                    f"Cannot determine path for {package_path}, skipping"
                )
                continue

            for module_info in pkgutil.walk_packages(
                search_paths, prefix=f"{package_path}."
            ):
                module_name = module_info.name

                # Ищем *_ext.py или модули в extensions/
                is_extension = (
                    module_name.endswith("_ext")
                    or ".extensions." in module_name
                    or module_name.endswith(".extensions")
                )

                if is_extension:
                    try:
                        importlib.import_module(module_name)
                        log.debug(f"Loaded extension: {module_name}")
                        loaded += 1
                    except ImportError as e:
                        log.warning(f"Could not import {module_name}: {e}")

        if loaded:
            log.info(f"Autodiscover: loaded {loaded} extension module(s)")

        cls._autodiscover_done = True

    def __getattribute__(self, name: str):
        # Приватные атрибуты — без обработки
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        cache = object.__getattribute__(self, "_cache")

        # Возвращаем из кеша если уже обработано
        if name in cache:
            return cache[name]

        # Получаем значение
        try:
            value = object.__getattribute__(self, name)
        except AttributeError:
            raise AttributeError(f"Model '{name}' not found")

        # Если это класс модели — применяем расширения
        from backend.base.system.dotorm.dotorm.model import DotModel

        if isinstance(value, type) and issubclass(value, DotModel):
            extended = registry.apply_to_model(value)
            cache[name] = extended
            return extended

        return value


# ============== EXTENSIBLE MODELS CORE ==============

# Импортируем ModelsCore для создания готового класса
from backend.base.system.core.models import ModelsCore


class ExtensibleModelsCore(ExtensibleMixin, ModelsCore):
    """
    Готовый класс ModelsCore с поддержкой расширений.

    Комбинирует ModelsCore + ExtensibleMixin.

    Example:
        class Models(ExtensibleModelsCore):
            lead = Lead
            partner = Partner

        env.models = Models()
        env.models.lead  # Lead с применёнными @extend расширениями
    """

    pass


# ============== УТИЛИТЫ ==============


def call_original(instance, method_name: str, *args, **kwargs):
    """
    Вызвать оригинальный метод модели (до применения расширений).

    Используется когда в расширении нужно вызвать родительскую реализацию.

    Пример:
        @extend(Lead)
        class LeadExtension:
            async def create(self, *args, **kwargs):
                # Вызываем оригинальный create
                result = await call_original(self, 'create', *args, **kwargs)
                # Делаем что-то после
                await self.send_notification()
                return result
    """
    model_class = type(instance)
    original = registry.get_original_method(model_class, method_name)

    if original:
        return original(instance, *args, **kwargs)

    raise AttributeError(
        f"Original method '{method_name}' not found for {model_class.__name__}"
    )


def get_extended_fields(model_class: Type) -> Dict[str, Any]:
    """
    Получить все поля модели, включая добавленные через @extend и унаследованные из миксинов.

    Гарантирует что расширения применены перед получением полей.
    """
    # Убеждаемся что расширения применены
    model_class = registry.apply_to_model(model_class)

    # Используем get_all_fields если есть, иначе fallback на MRO
    if hasattr(model_class, "get_all_fields"):
        return model_class.get_all_fields()

    # Fallback: собираем поля из всей цепочки наследования (MRO)
    from backend.base.system.dotorm.dotorm.fields import Field

    fields = {}
    for klass in reversed(model_class.__mro__):
        if klass is object:
            continue
        for attr_name, attr in klass.__dict__.items():
            if isinstance(attr, Field):
                fields[attr_name] = attr

    return fields
