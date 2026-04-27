# Copyright 2025 FARA CRM
# Chat module - helper for posting system messages (joins/leaves/etc.)

import json
import logging
from typing import TYPE_CHECKING, Any

from backend.base.crm.users.models.users import SYSTEM_USER_ID

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

log = logging.getLogger(__name__)


async def post_system_message(
    env: "Environment",
    chat_id: int,
    event: str,
    params: dict[str, Any] | None = None,
) -> None:
    """
    Создать системное сообщение чата и разослать его подписчикам через WS.

    Системные сообщения — события уровня чата (участник добавлен/удалён,
    покинул чат и т.п.), которые на фронте отображаются пилюлей в стиле
    Telegram: без аватара, без пузыря, без автора.

    В поле `body` кладётся JSON со структурой `{"event": "...",
    "params": {...}}`. Человекочитаемую строку формирует фронт через
    i18n — это даёт локализацию, возможность менять формулировку без
    миграций БД и устойчивость к переименованию пользователей.

    На бэке сообщение сохраняется с `message_type="system"` и
    `author_user_id=None`.

    Errors:
        Логирует warning и возвращает управление — не бросает наружу,
        чтобы сбой в cosmetics не ронял основную операцию чата.
    """

    try:
        payload = {"event": event, "params": params or {}}
        body = json.dumps(payload, ensure_ascii=False)

        message = await env.models.chat_message.post_message(
            chat_id=chat_id,
            author_user_id=SYSTEM_USER_ID,
            body=body,
            message_type="system",
        )

        await env.apps.chat.chat_manager.send_to_chat(
            chat_id=chat_id,
            message={
                "type": "new_message",
                "chat_id": chat_id,
                "message": {
                    "id": message.id,
                    "body": body,
                    "message_type": "system",
                    "author": {
                        "id": SYSTEM_USER_ID,
                        "name": None,
                        "type": "user",
                    },
                    "create_datetime": message.create_datetime.isoformat(),
                    "starred": False,
                    "pinned": False,
                    "is_edited": False,
                    "is_read": False,
                    "attachments": [],
                },
            },
        )
    except Exception as exc:
        log.warning(
            "post_system_message failed: chat_id=%s event=%s params=%s err=%s",
            chat_id,
            event,
            params,
            exc,
        )
