# Copyright 2025 FARA CRM
# Chat Phone module - base phone message adapter

from datetime import datetime, timezone

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class PhoneMessageAdapter(ChatMessageAdapter):
    """
    Базовый адаптер для парсинга событий звонков от телефонных провайдеров.

    Расширяет ChatMessageAdapter свойствами специфичными для телефонии.
    Конкретные провайдеры (Sipuni, Mango, etc.) наследуют этот класс
    и реализуют парсинг своего формата.

    Жизненный цикл звонка (события):
    1. Ringing (event_type='ringing') — начало дозвона
    2. Answered (event_type='answered') — сняли трубку, идёт разговор
    3. Ended (event_type='ended') — завершение (с disposition)

    Каждое событие создаёт или обновляет сообщение в чате.
    """

    # Дополнительные телефонные свойства
    @property
    def event_type(self) -> str:
        """
        Тип события звонка.

        Returns:
            'ringing' — начало дозвона
            'answered' — ответ на звонок
            'ended' — завершение звонка
        """
        raise NotImplementedError()

    @property
    def call_direction(self) -> str:
        """
        Направление звонка.

        Returns:
            'incoming' или 'outgoing'
        """
        raise NotImplementedError()

    @property
    def disposition(self) -> str:
        """
        Статус завершения звонка.

        Returns:
            'answered', 'no_answer', 'busy', 'failed', 'cancelled'
        """
        return "answered"

    @property
    def call_duration(self) -> int | None:
        """Общая длительность звонка в секундах."""
        return None

    @property
    def talk_duration(self) -> int | None:
        """Длительность разговора в секундах (после снятия трубки)."""
        return None

    @property
    def call_answer_timestamp(self) -> int | None:
        """Unix timestamp момента ответа на звонок."""
        return None

    @property
    def call_end_timestamp(self) -> int | None:
        """Unix timestamp момента завершения звонка."""
        return None

    @property
    def call_record_url(self) -> str | None:
        """URL записи разговора у провайдера (для скачивания)."""
        return None

    @property
    def caller_number(self) -> str:
        """Номер звонящего (клиент при входящем, оператор при исходящем)."""
        raise NotImplementedError()

    @property
    def callee_number(self) -> str:
        """Номер вызываемого (оператор при входящем, клиент при исходящем)."""
        raise NotImplementedError()

    @property
    def internal_number(self) -> str | None:
        """Внутренний номер/extension оператора."""
        return None

    # Свойства ChatMessageAdapter

    @property
    def is_from_external(self) -> bool:
        """
        Для телефонии: входящий звонок = от внешнего (клиента).
        Исходящий = от оператора (не внешний).
        """
        return self.call_direction == "incoming"

    @property
    def author_id(self) -> str:
        """
        ID автора — номер телефона звонящего.
        Для входящего: номер клиента.
        Для исходящего: номер клиента (кому звоним).
        """
        if self.call_direction == "incoming":
            return self.caller_number
        return self.callee_number

    @property
    def author_name(self) -> str | None:
        """Имя автора — номер телефона (имя определится через Contact)."""
        return self.author_id

    @property
    def text(self) -> str | None:
        """
        HTML-блок для отображения в чате.
        Генерируется на основе типа события.
        """
        return self._build_call_body()

    @property
    def images(self) -> list[str]:
        """Звонки не содержат изображений."""
        return []

    @property
    def files(self) -> list[dict]:
        """Аудиозапись (если есть) обрабатывается отдельно через стратегию."""
        return []

    # Вспомогательные методы

    def _build_call_body(self) -> str:
        """
        Построить HTML-блок для отображения звонка в чате.

        Возвращает компактный блок с иконкой и статусом.
        """
        direction_icon = "📞" if self.call_direction == "incoming" else "📱"
        direction_text = (
            "Входящий" if self.call_direction == "incoming" else "Исходящий"
        )

        if self.event_type == "ringing":
            return (
                f'<div class="call-message call-ringing">'
                f"{direction_icon} {direction_text} звонок — дозвон..."
                f"</div>"
            )

        if self.event_type == "answered":
            return (
                f'<div class="call-message call-active">'
                f"{direction_icon} {direction_text} звонок — разговор..."
                f"</div>"
            )

        # ended
        if self.disposition == "answered":
            duration_str = self._format_duration(self.talk_duration)
            return (
                f'<div class="call-message call-answered">'
                f"{direction_icon} {direction_text} звонок — {duration_str}"
                f"</div>"
            )

        disposition_map = {
            "no_answer": "Пропущенный",
            "busy": "Занято",
            "failed": "Ошибка",
            "cancelled": "Отменён",
        }
        status = disposition_map.get(self.disposition, self.disposition)
        return (
            f'<div class="call-message call-missed">'
            f"{direction_icon} {direction_text} звонок — {status}"
            f"</div>"
        )

    @staticmethod
    def _format_duration(seconds: int | None) -> str:
        """Форматировать секунды в HH:MM:SS."""
        if not seconds:
            return "00:00"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def _timestamp_to_datetime(ts: int | None) -> datetime | None:
        """Конвертировать unix timestamp в datetime UTC."""
        if ts:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return None
