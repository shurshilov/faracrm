from abc import ABC, abstractmethod


class AuthStrategyAbstract(ABC):
    @abstractmethod
    async def verify_access(self, *args, **kwargs):
        raise NotImplementedError

    # @abstractmethod
    # async def session_store_to_request():
    #     raise NotImplementedError
