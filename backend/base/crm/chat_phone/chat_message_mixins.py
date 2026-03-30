# Copyright 2025 FARA CRM
# Chat Phone module - ChatMessage mixin for call fields

from datetime import datetime
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_message import ChatMessage
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Datetime,
    Selection,
)

if TYPE_CHECKING:
    _Base = ChatMessage
else:
    _Base = object


@extend(ChatMessage)
class ChatMessagePhoneMixin(_Base):
    """
    Миксин для ChatMessage с поддержкой телефонных звонков.

    Добавляет:
    - Поля специфичные для звонков (direction, disposition, duration, etc.)

    Звонок = сообщение в чате с type='call' и дополнительными полями.
    При этом:
    - author_user_id/author_partner_id = кто инициировал/принял звонок
    - attachment_ids = аудиозапись разговора
    - external_message_ids = ID звонка у провайдера (call_id)
    - connector_id = через какой коннектор (Sipuni, Mango, etc.)
    - body = HTML-блок со статусом звонка (для отображения в чате)
    """

    call_direction: str | None = Selection(
        options=[
            ("incoming", "Incoming"),
            ("outgoing", "Outgoing"),
        ],
        description=(
            "Направление звонка. "
            "Нельзя однозначно определить из author при переводах звонков"
        ),
    )

    call_disposition: str | None = Selection(
        options=[
            ("ringing", "Ringing"),
            ("answered", "Answered"),
            ("no_answer", "No Answer"),
            ("busy", "Busy"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        description=(
            "Статус завершения звонка. "
            "Обновляется по мере прохождения событий от АТС"
        ),
    )

    # Длительность всего звонка (от начала дозвона до завершения), секунды
    call_duration: int | None = Integer(
        description="Общая длительность звонка в секундах",
    )

    # Длительность разговора (от снятия трубки до завершения), секунды
    call_talk_duration: int | None = Integer(
        description="Длительность разговора в секундах (после ответа)",
    )

    # Когда сняли трубку
    call_answer_time: "datetime | None" = Datetime(
        description="Время ответа на звонок (когда сняли трубку)",
    )

    # Когда повесили трубку
    call_end_time: "datetime | None" = Datetime(
        description="Время завершения звонка",
    )
