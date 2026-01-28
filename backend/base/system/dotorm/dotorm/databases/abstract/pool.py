"""Abstract pool interface."""

from abc import ABC, abstractmethod


class PoolAbstract(ABC):
    @abstractmethod
    async def create_pool(
        self,
    ): ...
