import asyncio
import logging
import time

try:
    import asynch
except ImportError:
    ...

from ..abstract.types import (
    ClickhousePoolSettings,
    ContainerSettings,
)

log = logging.getLogger(__package__)


class ContainerClickhouse:
    def __init__(
        self,
        pool_settings: ClickhousePoolSettings,
        container_settings: ContainerSettings,
    ):
        self.pool_settings = pool_settings
        self.container_settings = container_settings

    async def create_pool(self):
        try:
            start_time: float = time.time()
            pool = await asynch.create_pool(
                **self.pool_settings.model_dump(),
                min_size=5,
                max_size=15,
                # command_timeout=60,
                # 15 minutes
                # max_inactive_connection_lifetime
                # pool_recycle=60 * 15,
            )
            assert isinstance(pool, asynch.Pool)
            assert pool is not None
            self.pool = pool
            start_time: float = time.time()

            log.debug(
                "Connection Clickhouse db: %s, created time: [%0.3fs]",
                self.pool_settings.database,
                time.time() - start_time,
            )
            return self.pool
        except (ConnectionError, TimeoutError):
            # Если не смогли подключиться к базе пробуем переподключиться
            log.exception(
                "Clickhouse create poll connection lost, reconnect after 10 seconds: "
            )
            await asyncio.sleep(self.container_settings.reconnect_timeout)
            await self.create_pool()
        except Exception as e:
            # если ошибка не связанна с сетью, завершаем выполнение программы
            log.exception("Clickhouse create pool error:")
            raise e
