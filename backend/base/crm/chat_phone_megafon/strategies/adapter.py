# Copyright 2025 FARA CRM
# Chat Phone MegaFon module - MegaFon VATS webhook adapter

from backend.base.crm.chat_phone.strategies.adapter import PhoneMessageAdapter


class MegafonPhoneAdapter(PhoneMessageAdapter):
    """
    Адаптер для парсинга webhook команд от MegaFon VATS.

    MegaFon отправляет POST запросы с полем 'cmd', определяющим тип команды.

    Команда 'event' (real-time события):
    {
        "cmd": "event",
        "direction": "in",          # in/out
        "callid": "O3VUIAUSQ400004A",
        "diversion": "71117772211", # номер назначения (наш номер)
        "ext": "701",               # extension оператора
        "phone": "79997772211",     # номер клиента
        "type": "ACCEPTED",         # INCOMING/ACCEPTED/COMPLETED/CANCELLED/OUTGOING/TRANSFERRED
        "user": "admin",            # логин оператора
        "telnum": "71117772211",    # номер линии
        "crm_token": "..."
    }

    Команда 'history' (завершённый звонок):
    {
        "cmd": "history",
        "callid": "O3VUIAUSQ400004A",
        "start": "20260323T085626Z",
        "duration": "28",
        "wait": "10",
        "link": "https://...mp3",   # URL записи
        "telnum": "71117772211",
        "user": "admin",
        "type": "in",               # in/out
        "status": "Success",        # Success/missed/cancel/busy/...
        "phone": "79997772211",     # номер клиента
        "diversion": "71117772211",
        "ext": "701"
    }
    """

    @property
    def cmd(self) -> str:
        """Команда MegaFon: event/history/contact/rating."""
        return self.raw.get("cmd", "")

    @property
    def event_type(self) -> str:
        """
        Маппинг команд и событий MegaFon → lifecycle звонка.

        cmd=event + type=INCOMING  → ringing
        cmd=event + type=ACCEPTED  → answered
        cmd=event + type=COMPLETED → ended
        cmd=event + type=CANCELLED → ended
        cmd=event + type=OUTGOING  → ringing (исходящий)
        cmd=history                → ended (финальная запись)
        """
        if self.cmd == "history":
            return "ended"

        if self.cmd == "event":
            event = self.raw.get("type", "")
            mapping = {
                "INCOMING": "ringing",
                "OUTGOING": "ringing",
                "ACCEPTED": "answered",
                "COMPLETED": "ended",
                "CANCELLED": "ended",
                "TRANSFERRED": "answered",
            }
            return mapping.get(event, "ended")

        return "ended"

    @property
    def call_direction(self) -> str:
        """
        Направление звонка.

        cmd=event: поле direction ('in'/'out')
        cmd=history: поле type ('in'/'out')
        """
        if self.cmd == "event":
            return (
                "incoming" if self.raw.get("direction") == "in" else "outgoing"
            )
        # history
        return (
            "incoming"
            if self.raw.get("type", "").lower() == "in"
            else "outgoing"
        )

    @property
    def disposition(self) -> str:
        """
        Маппинг статуса MegaFon → disposition.

        event types → disposition:
        - COMPLETED → answered
        - CANCELLED → cancelled

        history statuses → disposition:
        - success → answered
        - missed → no_answer
        - cancel → cancelled
        - busy → busy
        - notavailable/notallowed/notfound → failed
        """
        if self.cmd == "event":
            event = self.raw.get("type", "")
            if event in ("COMPLETED", "ACCEPTED", "TRANSFERRED"):
                return "answered"
            if event == "CANCELLED":
                return "cancelled"
            if event in ("INCOMING", "OUTGOING"):
                return "ringing"
            return "failed"

        # history
        status = self.raw.get("status", "").lower()
        mapping = {
            "success": "answered",
            "missed": "no_answer",
            "cancel": "cancelled",
            "busy": "busy",
            "notavailable": "failed",
            "notallowed": "failed",
            "notfound": "failed",
        }
        return mapping.get(status, "failed")

    @property
    def caller_number(self) -> str:
        """Номер клиента."""
        return self.raw.get("phone", "")

    @property
    def callee_number(self) -> str:
        """Номер назначения (наш номер / diversion)."""
        return self.raw.get("diversion") or self.raw.get("telnum", "")

    @property
    def internal_number(self) -> str | None:
        """Extension оператора."""
        return self.raw.get("ext")

    @property
    def message_id(self) -> str:
        """ID звонка в MegaFon (callid)."""
        return str(self.raw.get("callid", ""))

    @property
    def chat_id(self) -> str:
        """ID чата = номер клиента (все звонки с одного номера → один чат)."""
        return self.author_id

    @property
    def author_name(self) -> str | None:
        """Имя — номер телефона клиента."""
        return self.caller_number or None

    @property
    def created_at(self) -> int:
        """
        Unix timestamp создания.
        MegaFon history: start в формате '20260323T085626Z'.
        MegaFon event: нет timestamp — используем текущее время.
        """
        start_str = self.raw.get("start")
        if start_str:
            try:
                from datetime import datetime

                dt = datetime.strptime(start_str, "%Y%m%dT%H%M%SZ")
                return int(dt.timestamp())
            except (ValueError, TypeError):
                pass
        return 0

    @property
    def call_duration(self) -> int | None:
        """
        Длительность звонка (только из history).
        Поле 'duration' — секунды.
        """
        duration = self.raw.get("duration")
        if duration:
            try:
                return int(duration)
            except (ValueError, TypeError):
                pass
        return None

    @property
    def talk_duration(self) -> int | None:
        """
        Длительность разговора = duration - wait.
        wait = время ожидания до ответа.
        """
        duration = self.call_duration
        wait = self.raw.get("wait")
        if duration and wait:
            try:
                talk = duration - int(wait)
                return max(0, talk)
            except (ValueError, TypeError):
                pass
        return duration if self.disposition == "answered" else None

    @property
    def call_answer_timestamp(self) -> int | None:
        """Время ответа = start + wait."""
        start_ts = self.created_at
        wait = self.raw.get("wait")
        if start_ts and wait:
            try:
                return start_ts + int(wait)
            except (ValueError, TypeError):
                pass
        return None

    @property
    def call_end_timestamp(self) -> int | None:
        """Время завершения = start + duration (только из history)."""
        start_ts = self.created_at
        duration = self.call_duration
        if start_ts and duration:
            return start_ts + duration
        return None

    @property
    def call_record_url(self) -> str | None:
        """URL записи разговора (только из history при status=success)."""
        if self.cmd == "history" and self.disposition == "answered":
            link = self.raw.get("link")
            if link and link.strip():
                return link
        return None

    @property
    def should_skip(self) -> bool:
        """
        Пропускаем:
        - Команды contact и rating (не звонки)
        - Пустой callid
        """
        if self.cmd in ("contact", "rating"):
            return True
        if not self.raw.get("callid"):
            return True
        return False
