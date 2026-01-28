# Copyright 2025 FARA CRM
# Chat module - strategies registry

from typing import Dict, Type
import logging

from .strategy import ChatStrategyBase
from .adapter import ChatMessageAdapter
from .internal import InternalStrategy, InternalMessageAdapter

logger = logging.getLogger(__name__)

# Реестр стратегий
_strategies: Dict[str, ChatStrategyBase] = {}


def register_strategy(strategy_class: Type[ChatStrategyBase]) -> None:
    """
    Зарегистрировать стратегию в реестре.

    Args:
        strategy_class: Класс стратегии (наследник ChatStrategyBase)
    """
    strategy = strategy_class()
    _strategies[strategy.strategy_type] = strategy
    logger.info(f"Registered chat strategy: {strategy.strategy_type}")


def get_strategy(strategy_type: str) -> ChatStrategyBase:
    """
    Получить стратегию по типу.

    Args:
        strategy_type: Тип стратегии (internal, telegram, whatsapp и т.д.)

    Returns:
        Экземпляр стратегии

    Raises:
        ValueError: Если стратегия не найдена
    """
    if strategy_type not in _strategies:
        raise ValueError(
            f"Unknown strategy type: {strategy_type}. "
            f"Available: {list(_strategies.keys())}"
        )
    return _strategies[strategy_type]


def list_strategies() -> list[str]:
    """Получить список зарегистрированных стратегий."""
    return list(_strategies.keys())


# Регистрируем встроенные стратегии
register_strategy(InternalStrategy)


__all__ = [
    # Base classes
    "ChatStrategyBase",
    "ChatMessageAdapter",
    # Internal
    "InternalStrategy",
    "InternalMessageAdapter",
    # Registry functions
    "register_strategy",
    "get_strategy",
    "list_strategies",
]
