# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - Asterisk / FreePBX webhook & CDR adapter

from datetime import datetime

from backend.base.crm.chat_phone.strategies.adapter import PhoneMessageAdapter


def _digits(value: str | None) -> str:
    """Только цифры из строки номера."""
    if not value:
        return ""
    return "".join(ch for ch in value if ch.isdigit())


class AsteriskPhoneAdapter(PhoneMessageAdapter):
    """
    Адаптер Asterisk / FreePBX.

    Понимает ДВА формата входящих данных (различаются по структуре):

    1) ARI-событие (живой сигнал, прилетает от Asterisk-agent на webhook):
       {
         "type": "ChannelStateChange" | "ChannelDestroyed" | "ChannelHangupRequest",
         "timestamp": "2024-05-11T16:04:53.044+0300",
         "channel": {
             "id": "1715432693.70626",              # uniqueid канала
             "name": "SIP/9624032060_out-000080ca",
             "state": "Down" | "Ring" | "Up",
             "caller":    {"name": "", "number": "+79614889972"},
             "connected": {"name": "", "number": ""},
             "dialplan":  {"app_name": "AppDial" | "", "exten": "...", ...}
         },
         "application": "AsteriskAgentPython"
       }
       Используется только для «живого» пузыря звонка (event_type=answered).
       Финализация (запись, длительность, disposition) приходит из CDR:
       на hangup стратегия до-запрашивает CDR по uniqueid у агента.

    2) CDR-запись (из истории звонков агента /api/calls/hisroty/):
       {
         "calldate": "2024-05-16T16:29:18",
         "src": "9624032060", "dst": "89624515599",
         "channel": "SIP/307-00008246",
         "dstchannel": "SIP/9624032060_out-00008247",
         "duration": 37, "billsec": 29,
         "disposition": "ANSWERED" | "NO ANSWER" | "BUSY" | "FAILED",
         "uniqueid": "1715866158.71448",
         "linkedid": "1715866158.71448",
         "recordingfile": "out-89624515599-307-...-....mp3",
         "lastapp": "Dial"
       }
       Это источник истины для сохранённого звонка (event_type=ended).
    """

    # ------------------------------------------------------------- shape
    @property
    def is_ari(self) -> bool:
        """
        ARI-событие гарантированно содержит строковое поле 'type' (например, 'StasisStart', 'Dial')
        и один из ключевых объектов ARI (channel, bridge, endpoint, или поле application).
        """
        raw_type = self.raw.get("type")
        if not isinstance(raw_type, str):
            return False

        # Список полей, которые встречаются только в иерархической структуре ARI JSON
        ari_indicators = {
            "channel",
            "bridge",
            "endpoint",
            "playback",
            "recording",
            "application",
        }

        # Если есть type И хотя бы один из индикаторов ARI структуры
        # ИЛИ если это специфичное событие вроде "Dial"
        if raw_type == "Dial" or any(
            key in self.raw for key in ari_indicators
        ):
            return True

        return False

    @property
    def _channel(self) -> dict:
        return self.raw.get("channel") or {}

    # --------------------------------------------------------- lifecycle
    @property
    def event_type(self) -> str:
        """
        Классифицирует тип события для CRM.
        Разделяет начало/процесс, ответ и реальное завершение звонка.
        """
        if not self.is_ari:
            # Для CDR записей из БД — это всегда историческое (завершенное) событие
            return "ended"

        etype = self.raw.get("type")
        channel = self.raw.get("channel") or {}
        dialplan = channel.get("dialplan") or {}

        # 1. Точное определение ответа (Ваша железная логика)
        if etype == "ChannelStateChange" and channel.get("state") == "Up":
            if dialplan.get("app_name") == "AppDial":
                caller_num = (channel.get("caller") or {}).get("number")
                connected_num = (channel.get("connected") or {}).get("number")
                if caller_num and connected_num:
                    return "answered"

        # 2. Точное определение НАСТОЯЩЕГО завершения звонка
        if etype == "ChannelDestroyed":
            return "ended"

        # 3. Все остальные события (StasisStart, Dial, BridgeEnter, HangupRequest)
        # Это рабочий процесс звонка, они не должны триггерить ни 'answered', ни 'ended'
        return "progress"

    # --------------------------------------------------------- direction
    @property
    def call_direction(self) -> str:
        """
        Направление звонка (ARI и CDR) по НАШИМ номерам.

        Приоритет:
        1. Префикс файла записи: out-… (исходящий) / in-… (входящий).
        2. По кэшу наших номеров (_is_internal → _our_numbers; до cache_numbers —
           fallback на длину ≤ 5):
           - оба наши          → "internal" (клиента НЕТ, звонок сотрудник↔сотрудник);
           - наш → не наш      → "outgoing";
           - не наш → наш      → "incoming";
           - оба чужие (транзит через АТС / мусор) → "incoming".
        """
        if self.is_ari:
            channel = self._channel
            dialplan = channel.get("dialplan") or {}
            src = (channel.get("caller") or {}).get("number") or ""
            dst = (
                (channel.get("connected") or {}).get("number")
                or dialplan.get("exten")
                or ""
            )
        else:
            src = self.raw.get("src") or ""
            dst = self.raw.get("dst") or ""

        # Спец-значения диалплана Asterisk (s=старт-экстеншен, h=hangup-хендлер,
        # unknown=нет CallerID) — это НЕ номер, обнуляем.
        if dst in ("h", "s", "unknown"):
            dst = ""

        recordingfile = (self.raw.get("recordingfile") or "").lower()
        if recordingfile.startswith("out-"):
            return "outgoing"
        if recordingfile.startswith("in-"):
            return "incoming"

        src_internal = self._is_internal(src)
        dst_internal = self._is_internal(dst)
        if src_internal and dst_internal:
            return "internal"  # оба наши → клиента нет
        if src_internal and not dst_internal:
            return "outgoing"
        # не наш → наш, либо оба чужие (транзит) → входящий
        return "incoming"

    # Множество номеров СОТРУДНИКОВ коннектора (цифры extension/number линий с
    # привязанным user_id), грузится в cache_numbers. None → не звали → fallback.
    _our_numbers: "set[str] | None" = None

    async def cache_numbers(self, env) -> None:
        """
        Загрузить номера СОТРУДНИКОВ коннектора (phone_number с привязанным
        user_id) в множество. По нему _is_internal = «это линия сотрудника».

        Непривязанная линия (extension без сотрудника) внутренней НЕ считается —
        звонок с/на такой номер идёт как клиентский (партнёр на этот номер). Один
        запрос на звонок.
        """
        rows = await env.models.phone_number.search(
            filter=[
                ("connector_id", "=", self.connector.id),
                ("user_id", "!=", None),
            ],
            fields=["extension", "number"],
        )
        nums: "set[str]" = set()
        for row in rows:
            for value in (row.extension, row.number):
                digits = _digits(value)
                if digits:
                    nums.add(digits)
        self._our_numbers = nums

    def _is_internal(self, number: str | None) -> bool:
        """
        Внутренний = номер СОТРУДНИКА (phone_number с user_id). До cache_numbers
        (номера ещё не загружены) — fallback на длину (≤ 5 цифр).
        """
        digits = _digits(number)
        if not digits:
            return False
        if self._our_numbers is not None:
            return digits in self._our_numbers
        return len(digits) <= 5

    # ------------------------------------------------------------ numbers
    @staticmethod
    def normalize_phone(number: str | None) -> str:
        """
        Канонизация номера клиента → E.164 (как Contact._canonicalize), чтобы
        ключ чата и матчинг совпадали с хранимыми контактами (вариант A).

        phonenumbers (libphonenumber), регион по умолчанию RU. Невалидные как
        телефон — как цифры (fallback, в т.ч. если библиотека недоступна).
        """
        if not number:
            return ""
        v = number.strip()
        try:
            import phonenumbers

            parsed = phonenumbers.parse(v, "RU")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                )
        except Exception:
            pass
        return _digits(v)

    @property
    def caller_number(self) -> str:
        """Инициатор звонка (src)."""
        if self.is_ari:
            return self._channel.get("caller", {}).get("number", "") or ""
        return self.raw.get("src", "") or ""

    @property
    def callee_number(self) -> str:
        """Вызываемый (dst)."""
        if self.is_ari:
            return self._channel.get("connected", {}).get("number", "") or ""
        return self.raw.get("dst", "") or ""

    @property
    def author_id(self) -> str:
        """
        Автор = нормализованный номер КЛИЕНТА.

        Входящий: клиент = caller (src).
        Исходящий: клиент = callee (dst).
        Нормализация → все звонки одного клиента ложатся в один чат.
        """
        if self.call_direction == "incoming":
            return self.normalize_phone(self.caller_number)
        return self.normalize_phone(self.callee_number)

    @property
    def internal_number(self) -> str | None:
        """Внутренний номер (extension) оператора."""
        if self.is_ari:
            return None
        src, dst = self.raw.get("src"), self.raw.get("dst")
        if self.call_direction == "outgoing" and self._is_internal(src):
            return _digits(src)
        if self.call_direction == "incoming" and self._is_internal(dst):
            return _digits(dst)
        return None

    # ---------------------------------------------------------------- ids
    @property
    def message_id(self) -> str:
        """
        Канонический id звонка (для связи событий одного звонка).

        CDR: linkedid (переживает переводы), fallback uniqueid.
        ARI: id канала. Для мерджа ARI-пузыря с CDR стратегия ищет
             существующее сообщение и по uniqueid тоже.
        """
        if self.is_ari:
            return str(self._channel.get("id", "") or "")
        return str(self.raw.get("linkedid") or self.raw.get("uniqueid") or "")

    @property
    def chat_id(self) -> str:
        """Чат = номер клиента (все звонки клиента → один чат)."""
        return self.author_id

    @property
    def author_name(self) -> str | None:
        """Имя автора — номер клиента (реальное имя определит Contact)."""
        return self.author_id or None

    # -------------------------------------------------------- disposition
    @property
    def disposition(self) -> str:
        if self.is_ari:
            return "answered"
        status = (self.raw.get("disposition") or "").upper()
        mapping = {
            "ANSWERED": "answered",
            "NO ANSWER": "no_answer",
            "NOANSWER": "no_answer",
            "BUSY": "busy",
            "FAILED": "failed",
            "CANCEL": "cancelled",
            "CONGESTION": "failed",
            "CHANUNAVAIL": "failed",
        }
        return mapping.get(status, "failed")

    # ------------------------------------------------------------- timing
    @property
    def _start_ts(self) -> int | None:
        raw_start = self.raw.get("calldate") or self.raw.get("start")
        if not raw_start:
            return None
        # Local-режим (прямой SQL, aiomysql/aiopg): calldate приходит уже как
        # datetime-объект (не строка) — берём timestamp напрямую. Иначе billsec
        # парсился, а calldate — нет, и время звонка становилось эпохой (1970).
        if isinstance(raw_start, datetime):
            return int(raw_start.timestamp())
        if isinstance(raw_start, (int, float)):
            return int(raw_start)
        # Remote-режим (JSON от агента): обычно "2024-05-16T16:29:18", но возможны
        # пробел вместо T, миллисекунды, таймзона. fromisoformat (py3.11+) съедает
        # все эти варианты; strptime — запасной.
        if isinstance(raw_start, str):
            iso = raw_start.strip().replace(" ", "T")
            try:
                return int(datetime.fromisoformat(iso).timestamp())
            except (ValueError, TypeError):
                pass
            try:
                return int(
                    datetime.strptime(
                        iso[:19], "%Y-%m-%dT%H:%M:%S"
                    ).timestamp()
                )
            except (ValueError, TypeError):
                return None
        return None

    @property
    def call_duration(self) -> int | None:
        value = self.raw.get("duration")
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @property
    def talk_duration(self) -> int | None:
        value = self.raw.get("billsec")
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @property
    def call_answer_timestamp(self) -> int | None:
        """Время ответа = старт + (duration - billsec)."""
        start = self._start_ts
        duration = self.call_duration
        billsec = self.talk_duration
        if start is not None and duration is not None and billsec:
            return start + max(0, duration - billsec)
        return None

    @property
    def call_end_timestamp(self) -> int | None:
        start = self._start_ts
        duration = self.call_duration
        if start is not None and duration is not None:
            return start + duration
        return None

    @property
    def created_at(self) -> int:
        return self._start_ts or 0

    # ---------------------------------------------------------- recording
    @property
    def recording_filename(self) -> str | None:
        """Имя файла записи для запроса к агенту (/api/call/recording/)."""
        return self.raw.get("recordingfile") or None

    @property
    def call_record_url(self) -> str | None:
        """
        Маркер наличия записи (триггер для базового _process_call_record).

        Для Asterisk это НЕ прямой URL — запись тянется через API агента
        по filename (см. AsteriskPhoneStrategy._download_call_record).
        Возвращаем имя файла как признак; реальный запрос строит стратегия.
        """
        if not self.is_ari and self.talk_duration and self.recording_filename:
            return self.recording_filename
        return None

    # --------------------------------------------------------------- skip
    @property
    def should_skip(self) -> bool:
        if self.is_ari:
            # ARI фильтруется в стратегии (_handle_ari_event)
            return False
        # CDR без id или без номеров — мусор
        if not (self.raw.get("linkedid") or self.raw.get("uniqueid")):
            return True
        if not self.raw.get("src") or not self.raw.get("dst"):
            return True
        return False
