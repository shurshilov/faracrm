# Copyright 2025 FARA CRM
# Chat Phone Asterisk - data sources (transport strategy: remote vs local)

from .base import AsteriskSourceBase
from .local import LocalAgentSource
from .remote import RemoteAgentSource


def get_source(connector) -> AsteriskSourceBase:
    """
    Выбрать источник данных по connector.agent_mode.

    'remote' (default) -> RemoteAgentSource (REST внешнего Asterisk-agent);
    'local'            -> LocalAgentSource  (прямой SQL к БД Asterisk + ARI).
    """
    if connector.agent_mode == "local":
        return LocalAgentSource(connector)
    return RemoteAgentSource(connector)


__all__ = [
    "AsteriskSourceBase",
    "RemoteAgentSource",
    "LocalAgentSource",
    "get_source",
]
