"""MySQL connection pool management."""

import asyncio
import logging
import time

try:
    import aiomysql
except ImportError:
    ...
from ..abstract.types import ContainerSettings, MysqlPoolSettings

log = logging.getLogger("dotorm")


class ContainerMysql:
    """
    MySQL connection pool container.

    Manages pool lifecycle.
    """

    def __init__(
        self,
        pool_settings: MysqlPoolSettings,
        container_settings: ContainerSettings,
    ):
        self.pool_settings = pool_settings
        self.container_settings = container_settings
        self.pool: "aiomysql.Pool | None" = None

    async def create_pool(self) -> "aiomysql.Pool":
        """Create connection pool; on connection loss retry after
        reconnect_timeout (a loop, not recursion — retries are unbounded)."""
        while True:
            try:
                start_time = time.time()
                self.pool = await aiomysql.create_pool(
                    **self.pool_settings.model_dump(),
                    minsize=5,
                    maxsize=15,
                    autocommit=True,
                    # 15 minutes
                    pool_recycle=60 * 15,
                )

                log.debug(
                    "Connection MySQL db: %s, created time: [%0.3fs]",
                    self.pool_settings.db,
                    time.time() - start_time,
                )
                return self.pool

            except (ConnectionError, TimeoutError, aiomysql.OperationalError):
                log.exception(
                    "MySQL create pool connection lost, reconnect after %d seconds",
                    self.container_settings.reconnect_timeout,
                )
                await asyncio.sleep(self.container_settings.reconnect_timeout)
            except Exception as e:
                log.exception("MySQL create pool error:")
                raise e

    async def close_pool(self):
        """Close connection pool."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
