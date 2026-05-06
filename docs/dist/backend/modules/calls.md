# Звонки <span class="tag tag-new">NEW</span>

WebRTC-звонки 1-на-1 между пользователями FARA. Сигналинг через существующий WebSocket чата, голосовой трафик — peer-to-peer через WebRTC. Если получатель не в сети, бэкенд пробует разбудить его через web push, а если и push не настроен — пишет о пропущенном звонке в чат.

## Концепция

Звонок — это `ChatMessage(message_type='call')` в direct-чате между двумя юзерами. Поля состояния (`call_direction`, `call_disposition`, `call_duration`, ...) задаются миксином `ChatMessagePhoneMixin` из модуля `chat_phone`.

Этот подход даёт сразу несколько вещей бесплатно:

- История звонков уже хранится — это просто чат-сообщения.
- Пропущенные звонки видны в чате как обычные пропущенные.
- Уведомления о звонках идут через тот же механизм, что и о сообщениях.
- Не нужны отдельные таблицы / модели / роутеры.

## Жизненный цикл

```mermaid
stateDiagram-v2
    [*] --> ringing: POST /calls/start
    ringing --> answered: callee accept
    ringing --> no_answer: timeout
    ringing --> cancelled: caller отменил
    answered --> answered: разговор
    answered --> [*]: POST /calls/{id}/end
    no_answer --> [*]
    cancelled --> [*]

    note right of ringing
        Пока ringing:
        - WS invite
        - 3s ack timeout
        - push wake (если нужен)
    end note
```

## Endpoints

<div class="endpoint endpoint-post" markdown>
<div class="endpoint-head" markdown>
<span class="method-post">POST</span>
`/calls/start`
<span class="endpoint-summary">Начать звонок</span>
</div>
<div class="endpoint-body" markdown>
**Body:** `{ "callee_user_id": int }`

**Response 200:**
```json
{
  "call_id": 123,
  "chat_id": 17,
  "callee": { "id": 42, "name": "Иван" }
}
```

**Response 409 (callee недоступен):**
```json
{
  "detail": {
    "reason": "no_push" | "push_no_answer",
    "message": "Callee is offline...",
    "call_id": 123,
    "chat_id": 17
  }
}
```

См. [Поток вызова](#поток-вызова) для деталей trade-off между WS / push.
</div>
</div>

<div class="endpoint endpoint-post" markdown>
<div class="endpoint-head" markdown>
<span class="method-post">POST</span>
`/calls/{call_id}/accept`
<span class="endpoint-summary">Принять звонок (callee)</span>
</div>
<div class="endpoint-body" markdown>
Только callee может принять (не автор call-сообщения).

Меняет `disposition='answered'`, шлёт `call.accepted` через WS звонящему.
</div>
</div>

<div class="endpoint endpoint-post" markdown>
<div class="endpoint-head" markdown>
<span class="method-post">POST</span>
`/calls/{call_id}/reject`
<span class="endpoint-summary">Отклонить или отменить</span>
</div>
<div class="endpoint-body" markdown>
- если reject делает callee → `disposition='no_answer'`
- если reject делает caller → `disposition='cancelled'`

В обоих случаях — `call.rejected` через WS другой стороне с `reason: "declined" | "cancelled"`.
</div>
</div>

<div class="endpoint endpoint-post" markdown>
<div class="endpoint-head" markdown>
<span class="method-post">POST</span>
`/calls/{call_id}/end`
<span class="endpoint-summary">Завершить активный звонок</span>
</div>
<div class="endpoint-body" markdown>
**Body:** `{ "duration_seconds": int? }`

Считает `call_duration` и `call_talk_duration`. Если клиент прислал свою длительность — уважает её (точнее серверной).
</div>
</div>

<div class="endpoint endpoint-get" markdown>
<div class="endpoint-head" markdown>
<span class="method-get">GET</span>
`/users/{user_id}/availability`
<span class="endpoint-summary">Узнать доступность</span>
</div>
<div class="endpoint-body" markdown>
**Response:** `{ "online": bool, "has_push": bool }`

Используется фронтом для отрисовки индикатора рядом с кнопкой «Позвонить»:

| online | has_push | UI |
|--------|----------|-----|
| ✓ | — | 🟢 Зелёная кнопка, звонок дойдёт мгновенно |
| — | ✓ | 🟡 Жёлтая, "Через push (до 20 сек)" |
| — | — | ⚪ Серая, "Сообщение в чат — он офлайн" |
</div>
</div>

## Поток вызова

```mermaid
sequenceDiagram
    participant C as Caller
    participant API as POST /calls/start
    participant WS as WebSocket
    participant P as Push
    participant CE as Callee

    C->>API: callee_user_id
    API->>API: создать call-сообщение<br/>disposition=ringing
    API->>WS: send_to_user(callee, "call.invite")
    API->>API: wait ack (3s)

    alt callee онлайн
        WS->>CE: call.invite
        CE->>WS: call.invite_ack
        WS-->>API: ack received
        API-->>C: 200 OK { call_id, chat_id }
    else callee оффлайн, есть push
        Note over API: timeout 3s истёк
        API->>P: send_call_invite()
        API->>API: wait ack (20s)
        P->>CE: системное уведомление<br/>с кнопками
        CE->>CE: PWA откроется на тапе
        CE->>WS: call.invite_ack
        WS-->>API: ack received
        API-->>C: 200 OK
    else callee оффлайн, без push
        API->>API: disposition=no_answer
        API-->>C: 409 { reason: "no_push" }
        Note over C: всплывашка<br/>"не в сети, нет уведомлений"
    else push отправили, но не ответил
        API->>API: disposition=no_answer
        API-->>C: 409 { reason: "push_no_answer" }
        Note over C: всплывашка<br/>"уведомлен, не подключился"
    end
```

## Push wake-up

Если первый таймаут истёк, и у callee есть активная подписка на web push (`Contact(contact_type=web_push)`), бэкенд через `WebPushStrategy.send_call_invite()` шлёт push с payload:

```json
{
  "kind": "call",
  "call_id": 123,
  "chat_id": 17,
  "caller": { "id": 42, "name": "Иван" },
  "tag": "call-123",
  "requireInteraction": true,
  "title": "Иван",
  "body": "Иван звонит…"
}
```

Service Worker на стороне callee видит `kind="call"` и показывает уведомление с кнопками «Принять / Отклонить» и вибрацией. На тап — открывает PWA с URL `?call_id=...&chat_id=...&auto=accept|reject`.

`NotificationBridge` на фронте парсит эти параметры и автоматически вызывает `acceptCall()` / `rejectCall()` как только в WS придёт `call.invite`.

!!! info "Web Push не звонит сам"
    SW не может проиграть звук без открытого окна — это политика всех браузеров. Уведомление + системный звук + вибрация — максимум, что доступно из самого пуша.

    Для «настоящего» VoIP-звонка с заблокированного экрана нужен нативный мобильный канал (FCM с категорией VoIP / APNS PushKit). PWA до этого не дотягивается. Если потребуется — оборачивать через Capacitor с CallKit.

## Pending invite — атомарный ack

Перед отправкой WS-инвайта, бэкенд регистрирует `asyncio.Event` в `chat_manager._pending_invites[call_id]`:

```python
ack_event = chat_manager._register_pending_invite(msg.id)

await chat_manager.send_to_user(callee_id, {
    "type": "call.invite",
    "call_id": msg.id,
    ...
})

try:
    await asyncio.wait_for(ack_event.wait(), timeout=_INVITE_ACK_TIMEOUT)
finally:
    chat_manager._cleanup_pending_invite(msg.id)
```

Когда callee получает invite, он шлёт `call.invite_ack` обратно. Хендлер этого сообщения:

```python
if message["type"] == "call.invite_ack":
    chat_manager._resolve_pending_invite(message["call_id"])
```

`_resolve_pending_invite` ставит соответствующий `Event`. Бэкенд просыпается из `wait_for` и продолжает.

Cross-process работает корректно: в pubsub летит и invite, и ack — оба воркера видят, какой `call_id` подтверждён.

## Сериализация call-сообщения

`_serialize_call_message()` приводит ChatMessage к формату, который фронт использует для обычных сообщений. Поля `call_*` встраиваются прямо в payload:

```json
{
  "id": 123,
  "message_type": "call",
  "author": { "id": 42, "name": "Иван", "type": "user" },
  "create_datetime": "2026-04-30T12:34:56Z",
  "call_direction": "outgoing",
  "call_disposition": "answered",
  "call_duration": 67,
  "call_talk_duration": 60,
  "call_answer_time": "2026-04-30T12:35:03Z",
  "call_end_time": "2026-04-30T12:36:03Z"
}
```

Так фронту не нужно делать отдельный запрос за деталями звонка — он рисует плашку прямо из ленты сообщений через `CallMessageContent`.

## WebRTC

Сам голосовой трафик идёт **peer-to-peer** через `RTCPeerConnection`. STUN-сервера от Google:

```javascript
const ICE_SERVERS = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
];
```

SDP offer/answer и ICE candidates ходят через тот же WebSocket чата как сообщения типа `webrtc.offer`, `webrtc.answer`, `webrtc.ice`. Бэкенд их просто пробрасывает через `send_to_user` — никакой логики, кроме маршрутизации, на сервере нет.

!!! warning "Без TURN — только когда оба не за NAT"
    STUN помогает узнать публичный IP, но не пробивает symmetric NAT. Если оба клиента в офисах с rigorous firewall — звонок не соединится. Production-решение — добавить TURN-сервер (например, [coturn](https://github.com/coturn/coturn)), и его координаты в `ICE_SERVERS`.

## Состояния звонка на фронте

```typescript
type CallState =
  | 'idle'        // нет активного звонка
  | 'calling'     // исходящий, ждём ack/accept
  | 'incoming'    // входящий, показываем UI
  | 'connecting'  // accepted, идёт SDP/ICE
  | 'active'      // разговор
  | 'ended';      // завершён, показываем итог
```

Хук `useWebRTCCall()` экспортирует `state`, `session`, `endReason`, плюс действия: `startCall`, `acceptCall`, `rejectCall`, `hangup`, `toggleMute`. Глобально подключается через `<CallProvider>` в корне приложения.

`<CallWidget />` рендерит UI всех фаз — плашка в правом нижнем углу. При `incoming` играет рингтон через Web Audio API (генерирует тон, не нужен mp3).

## Известные ограничения

- **Один звонок за раз** на пользователя — кнопка `<CallButton>` блокируется при `state != 'idle'`.
- **Только аудио** — видео не реализовано.
- **Group call отсутствует** — только 1-на-1 в `direct`-чате.
- **Запись** — нет (можно добавить через `MediaRecorder` API при необходимости).

## См. также

- [Чат — архитектура](chat-architecture.md) — WebSocket, pub/sub
- [Push wake-up на бэкенде](../system/cron.md) — общий механизм cron
