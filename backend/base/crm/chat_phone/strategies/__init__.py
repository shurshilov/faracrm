# Copyright 2025 FARA CRM
# Chat Phone module - strategies

from .strategy import PhoneStrategyBase
from .adapter import PhoneMessageAdapter
from .pipeline_incoming_call import IncomingCallPipeline

__all__ = [
    "PhoneStrategyBase",
    "PhoneMessageAdapter",
    "IncomingCallPipeline",
]
