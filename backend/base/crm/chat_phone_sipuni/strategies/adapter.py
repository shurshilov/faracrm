# Copyright 2025 FARA CRM
# Chat Phone Sipuni module - Sipuni webhook message adapter

from backend.base.crm.chat_phone.strategies.adapter import PhoneMessageAdapter


class SipuniPhoneAdapter(PhoneMessageAdapter):
    """
    Адаптер для парсинга webhook событий от Sipuni.

    Формат входящего события (GET параметры):
    {
        event: int — тип запроса (1=дозвон, 2=завершение, 3=ответ)
        call_id: str — уникальный ID вызова
        src_num: str — номер инициатора звонка
        src_type: int — тип адреса (1=внешний, 2=внутренний)
        dst_num: str — номер назначения
        dst_type: int — тип адреса назначения
        timestamp: int — unix timestamp события
        status: str — статус (ANSWER, NOANSWER, BUSY, CANCEL, etc.)
        call_start_timestamp: int — unix timestamp начала звонка
        call_answer_timestamp: str — unix timestamp ответа
        call_record_link: str — URL записи разговора
        short_src_num: str — короткий номер источника
        short_dst_num: str — короткий номер назначения
        treeName: str — название схемы (Продажи, Техподдержка)
        treeNumber: str — номер схемы
        last_called: str — последний вызванный внутренний номер
    }
    """

    @property
    def event_type(self) -> str:
        """
        Маппинг событий Sipuni → lifecycle звонка.

        Sipuni event codes:
        - 1: начало внутреннего дозвона (is_inner_call=1)
        - 2: завершение звонка
        - 3: ответ на звонок (сняли трубку)
        """
        event = self.raw.get("event")
        if event == 1:
            return "ringing"
        if event == 3:
            return "answered"
        if event == 2:
            return "ended"
        return "ended"

    @property
    def call_direction(self) -> str:
        """
        Определение направления звонка по типам src/dst.

        src_type=1 (внешний) + dst_type=2 (внутренний) → входящий
        src_type=2 (внутренний) + dst_type=1 (внешний) → исходящий
        src_type=1 + dst_type=1 → входящий (через транк)
        """
        src_type = self.raw.get("src_type")
        dst_type = self.raw.get("dst_type")

        if src_type == 2 and dst_type == 1:
            return "outgoing"
        # Все остальные комбинации считаем входящим
        return "incoming"

    @property
    def disposition(self) -> str:
        """
        Маппинг статуса Sipuni → disposition.

        Sipuni statuses: ANSWER, NOANSWER, BUSY, CANCEL,
        CONGESTION, CHANUNAVAIL
        """
        status = self.raw.get("status", "")
        mapping = {
            "ANSWER": "answered",
            "NOANSWER": "no_answer",
            "BUSY": "busy",
            "CANCEL": "cancelled",
            "CONGESTION": "failed",
            "CHANUNAVAIL": "failed",
        }
        return mapping.get(status, "failed")

    @property
    def caller_number(self) -> str:
        """Номер звонящего."""
        return self.raw.get("short_src_num") or self.raw.get("src_num", "")

    @property
    def callee_number(self) -> str:
        """Номер вызываемого."""
        return self.raw.get("short_dst_num") or self.raw.get("dst_num", "")

    @property
    def internal_number(self) -> str | None:
        """
        Внутренний номер оператора.

        При входящем: dst_num (если dst_type=2) или last_called
        При исходящем: src_num (если src_type=2)
        """
        if self.call_direction == "incoming":
            if self.raw.get("dst_type") == 2:
                return self.raw.get("short_dst_num")
            return self.raw.get("last_called")
        else:
            if self.raw.get("src_type") == 2:
                return self.raw.get("short_src_num")
        return None

    @property
    def message_id(self) -> str:
        """ID звонка в Sipuni (сохраняется при переводе)."""
        return str(self.raw.get("call_id", ""))

    @property
    def chat_id(self) -> str:
        """
        ID чата = номер клиента.

        Все звонки с одного номера попадают в один чат.
        """
        return self.author_id

    @property
    def created_at(self) -> int:
        """Unix timestamp события."""
        return int(self.raw.get("timestamp", 0))

    @property
    def call_duration(self) -> int | None:
        """
        Общая длительность — вычисляется из timestamps.

        Доступно только при event=2 (завершение).
        """
        start = self.raw.get("call_start_timestamp")
        end = self.raw.get("timestamp")
        if start and end:
            return int(end) - int(start)
        return None

    @property
    def talk_duration(self) -> int | None:
        """
        Длительность разговора — от ответа до завершения.

        Доступно только при event=2 и status=ANSWER.
        """
        answer = self.raw.get("call_answer_timestamp")
        end = self.raw.get("timestamp")
        if answer and end and self.raw.get("status") == "ANSWER":
            return int(end) - int(answer)
        return None

    @property
    def call_answer_timestamp(self) -> int | None:
        """Unix timestamp ответа на звонок."""
        ts = self.raw.get("call_answer_timestamp")
        if ts:
            return int(ts)
        return None

    @property
    def call_end_timestamp(self) -> int | None:
        """Unix timestamp завершения (только для event=2)."""
        if self.raw.get("event") == 2:
            return int(self.raw.get("timestamp", 0))
        return None

    @property
    def call_record_url(self) -> str | None:
        """
        URL записи разговора.

        Доступен только при event=2 и status=ANSWER.
        """
        if (
            self.raw.get("event") == 2
            and self.raw.get("status") == "ANSWER"
            and self.raw.get("call_record_link")
        ):
            return self.raw.get("call_record_link")
        return None

    @property
    def should_skip(self) -> bool:
        """
        Пропускаем события без call_id или внутренние переводы.

        event=1 с is_inner_call=0 — это служебное событие маршрутизации.
        """
        if not self.raw.get("call_id"):
            return True

        # event=1 без is_inner_call — служебный вызов
        if self.raw.get("event") == 1:
            if not int(self.raw.get("is_inner_call", 0)):
                return True

        return False
