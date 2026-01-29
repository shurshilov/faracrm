# Copyright 2025 FARA CRM
# Attachments module - storage strategies registry

from typing import Dict, Type, List
import logging

from .strategy import StorageStrategyBase

logger = logging.getLogger(__name__)

# Реестр стратегий хранения
_strategies: Dict[str, StorageStrategyBase] = {}


def register_strategy(strategy_class: Type[StorageStrategyBase]) -> None:
    """
    Зарегистрировать стратегию в реестре.

    Args:
        strategy_class: Класс стратегии (наследник StorageStrategyBase)

    Raises:
        ValueError: Если стратегия с таким типом уже зарегистрирована
    """
    strategy = strategy_class()

    if not strategy.strategy_type:
        raise ValueError(
            f"Strategy class {strategy_class.__name__} must define strategy_type"
        )

    if strategy.strategy_type in _strategies:
        logger.warning(
            f"Strategy '{strategy.strategy_type}' already registered, "
            f"replacing with {strategy_class.__name__}"
        )

    _strategies[strategy.strategy_type] = strategy
    logger.info(f"Registered storage strategy: {strategy.strategy_type}")


def get_strategy(strategy_type: str) -> StorageStrategyBase:
    """
    Получить стратегию по типу.

    Args:
        strategy_type: Тип стратегии (file, google, onedrive и т.д.)

    Returns:
        Экземпляр стратегии

    Raises:
        ValueError: Если стратегия не найдена
    """
    if strategy_type not in _strategies:
        available = list(_strategies.keys())
        raise ValueError(
            f"Unknown storage strategy: '{strategy_type}'. "
            f"Available strategies: {available}"
        )
    return _strategies[strategy_type]


def list_strategies() -> List[str]:
    """
    Получить список зарегистрированных стратегий.

    Returns:
        Список типов зарегистрированных стратегий
    """
    return list(_strategies.keys())


def has_strategy(strategy_type: str) -> bool:
    """
    Проверить, зарегистрирована ли стратегия.

    Args:
        strategy_type: Тип стратегии

    Returns:
        True если стратегия зарегистрирована
    """
    return strategy_type in _strategies


def get_all_strategies() -> Dict[str, StorageStrategyBase]:
    """
    Получить все зарегистрированные стратегии.

    Returns:
        Словарь {тип: экземпляр стратегии}
    """
    return _strategies.copy()


# Импорт и регистрация встроенной стратегии filestore
from .filestore import FileStoreStrategy

register_strategy(FileStoreStrategy)


__all__ = [
    # Base class
    "StorageStrategyBase",
    # FileStore strategy
    "FileStoreStrategy",
    # Registry functions
    "register_strategy",
    "get_strategy",
    "list_strategies",
    "has_strategy",
    "get_all_strategies",
]
