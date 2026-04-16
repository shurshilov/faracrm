# Copyright 2025 FARA CRM
# Chat module - messages router

from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request, Query
from starlette.status import HTTP_403_FORBIDDEN

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.chat.websocket import chat_manager
from backend.base.crm.chat_web_push.notification_service import (
    notify_on_new_message,
)
from backend.base.system.core.exceptions.environment import FaraException
from ..schemas.chat import (
    MessageCreate,
    MessageEdit,
    MessagePin,
    MessageForward,
    MessageReaction,
)
from ..models.chat_member import ChatMember

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session

router_private = APIRouter(
    tags=["Chat"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


def format_message_author(msg) -> dict:
    """
    Форматирует автора сообщения (user или partner).
    """
    if msg.author_user_id:
        return {
            "id": msg.author_user_id.id,
            "name": msg.author_user_id.name,
            "type": "user",
        }
    elif msg.author_partner_id:
        return {
            "id": msg.author_partner_id.id,
            "name": msg.author_partner_id.name,
            "type": "partner",
        }
    return {"id": None, "name": "Unknown", "type": None}


@router_private.get("/chats/{chat_id}/messages")
async def get_messages(
    req: Request,
    chat_id: int,
    limit: int = Query(50, ge=1, le=100),
    before_id: int | None = Query(None),
    include_deleted: int = Query(0, description="Admin: показать удалённые"),
):
    """
    Получить сообщения чата.
    Требует права can_read.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство (can_read по умолчанию true) и получаем member
    current_member = await ChatMember.check_membership(chat_id, user_id)

    # Soft-delete: показывать удалённые только админам
    _is_admin = auth_session.user_id.is_admin or current_member.is_admin
    _show_deleted = bool(include_deleted) and _is_admin

    messages = await env.models.chat_message.get_chat_messages(
        chat_id=chat_id,
        limit=limit,
        before_id=before_id,
        include_deleted=_show_deleted,
    )

    last_read_watermark: int = current_member.last_read_message_id or 0

    # Получаем ID всех сообщений для загрузки аттачментов и реакций
    message_ids = [msg.id for msg in messages]

    # Загружаем аттачменты для всех сообщений одним запросом
    attachments_by_message: dict[int, list] = {}
    if message_ids:
        attachments = await env.models.attachment.search(
            filter=[
                ("res_model", "=", "chat_message"),
                ("res_id", "in", message_ids),
            ],
            fields=[
                "id",
                "name",
                "mimetype",
                "size",
                "checksum",
                "res_id",
                "is_voice",
                "show_preview",
            ],
        )
        for att in attachments:
            msg_id = att.res_id
            if msg_id is None:
                continue
            if msg_id not in attachments_by_message:
                attachments_by_message[msg_id] = []
            attachments_by_message[msg_id].append(
                {
                    "id": att.id,
                    "name": att.name,
                    "mimetype": att.mimetype,
                    "size": att.size,
                    "checksum": att.checksum,
                    "is_voice": att.is_voice or False,
                    "show_preview": att.show_preview,
                }
            )

    # Загружаем реакции для всех сообщений одним запросом
    reactions_by_message: dict[int, dict[str, list]] = {}
    if message_ids:
        reactions = await env.models.chat_message_reaction.search(
            filter=[("message_id", "in", message_ids)],
            fields=["id", "emoji", "message_id", "user_id"],
        )
        for reaction in reactions:
            msg_id = reaction.message_id.id
            if msg_id not in reactions_by_message:
                reactions_by_message[msg_id] = {}
            emoji = reaction.emoji
            if emoji not in reactions_by_message[msg_id]:
                reactions_by_message[msg_id][emoji] = []
            reactions_by_message[msg_id][emoji].append(
                {
                    "user_id": reaction.user_id.id,
                    "user_name": reaction.user_id.name,
                }
            )

    # Преобразуем реакции в нужный формат
    def format_reactions(msg_id: int) -> list:
        if msg_id not in reactions_by_message:
            return []
        return [
            {"emoji": emoji, "users": users, "count": len(users)}
            for emoji, users in reactions_by_message[msg_id].items()
        ]

    result = []
    for msg in messages:
        # is_read вычисляется из watermark: сообщение прочитано, если его
        # id <= last_read_watermark. Своё сообщение всегда считаем
        # прочитанным (автор его видел, ведь он его написал).
        is_own = msg.author_user_id and msg.author_user_id.id == user_id
        computed_is_read = is_own or (msg.id <= last_read_watermark)

        msg_data = {
            "id": msg.id,
            "body": msg.body,
            "message_type": msg.message_type,
            "create_date": msg.create_date.isoformat(),
            "starred": msg.starred,
            "pinned": msg.pinned,
            "is_edited": msg.is_edited,
            "is_read": computed_is_read,
            "parent_id": msg.parent_id,
            "connector_id": msg.connector_id,
            "author": format_message_author(msg),
            "attachments": attachments_by_message.get(msg.id, []),
            "reactions": format_reactions(msg.id),
            "is_deleted": msg.is_deleted is True,
        }

        result.append(msg_data)

    return {"data": result}


@router_private.get("/chats/messages/count")
async def get_messages_count(
    req: Request,
    res_model: str = Query(
        ..., description="Модель записи (partner, lead, ...)"
    ),
    res_id: int = Query(..., description="ID записи"),
):
    """
    Количество chat_message в record-чате записи `res_model`/`res_id`.

    Логика: находим record-чат по (res_model, res_id), считаем
    сообщения в нём. res_model/res_id живут только у chat — у сообщения
    их нет. Это избегает дублирования и рассинхронизации.

    Зачем отдельный эндпоинт: auto-CRUD для chat_message отключён
    (ChatMessage.__auto_crud__ = False) — писать/читать сообщения можно
    только через /chats/... с проверкой прав ChatMember. А для бейджика
    на карточке партнёра/сделки нужен только счётчик.

    Безопасность: отдаём только число. Доступ к самой карточке уже
    проверен Rules-ами соответствующей модели.
    """
    env: "Environment" = req.app.state.env

    # Если record-чата ещё нет (никто не подписывался) — сообщений нет.
    chat_record = await env.models.chat.search(
        filter=[
            ("res_model", "=", res_model),
            ("res_id", "=", res_id),
            ("chat_type", "=", "record"),
            ("active", "=", True),
        ],
        fields=["id"],
        limit=1,
    )
    if not chat_record:
        return {"total": 0}

    total = await env.models.chat_message.search_count(
        filter=[
            ("chat_id", "=", chat_record[0].id),
            ("is_deleted", "=", False),
        ]
    )
    return {"total": total}


@router_private.post("/chats/{chat_id}/messages")
async def post_message(req: Request, chat_id: int, body: MessageCreate):
    """
    Отправить сообщение в чат с вложениями.
    Требует права can_write.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем что есть текст или вложения
    if not body.body.strip() and not body.attachments:
        raise FaraException({"content": "EMPTY_MESSAGE"})

    # Проверяем право на отправку сообщений
    await ChatMember.check_can_write(chat_id, user_id)

    async with env.apps.db.get_transaction() as session:
        # Создаём сообщение внутреннее
        message = await env.models.chat_message.post_message(
            chat_id=chat_id,
            author_user_id=user_id,
            body=body.body,
            connector_id=body.connector_id,
            parent_id=body.parent_id,
        )

        # Создаём аттачменты и привязываем к сообщению.
        attachments_content_data: list[Attachment] = []
        attachments_response: list[dict] = []
        if body.attachments:
            payloads: list[Attachment] = [
                env.models.attachment(
                    name=file_data.name,
                    mimetype=file_data.mimetype,
                    size=file_data.size,
                    # size=len(file_data.content),
                    content=file_data.content,  # уже bytes
                    res_model="chat_message",
                    res_id=message.id,
                    is_voice=file_data.is_voice,
                )
                for file_data in body.attachments
            ]
            records = await env.models.attachment.create_bulk(
                payloads, session=session
            )
            # records — список записей [{id: ...}, ...] в том же порядке,
            # что и payloads. Для внешней отправки (Telegram/WhatsApp и т.д.)
            # передаём payloads как есть — у них в content уже bytes.
            for payload, record in zip(payloads, records or []):
                payload.id = record["id"]
                attachments_content_data.append(payload)

        attachments_response = [
            {
                "id": a.id,
                "name": a.name,
                "mimetype": a.mimetype,
                "size": a.size,
                "is_voice": a.is_voice,
                "storage_file_url": a.storage_file_url,
                "checksum": a.checksum,
                "show_preview": a.show_preview,
            }
            for a in attachments_content_data
        ]

        # Если указан connector_id - отправляем во внешний сервис
        if body.connector_id:
            connector = await env.models.chat_connector.get(body.connector_id)
            if not connector or not connector.active:
                return False

            # Собираем recipients_ids - контакты партнёров чата,
            # которые подходят под тип коннектора
            # Используем contact_type_id коннектора (integer FK)
            connector_contact_type_id = connector.contact_type_id

            recipients_ids = []
            if connector_contact_type_id:
                # Находим контакты партнёров-участников чата
                session = env.apps.db.get_session()
                recipients_query = """
                    SELECT c.id, c.name as contact_value
                    FROM chat_member cm
                    JOIN contact c ON c.partner_id = cm.partner_id
                        AND c.active = true
                        AND c.contact_type_id = %s
                    WHERE cm.chat_id = %s
                      AND cm.partner_id IS NOT NULL
                      AND cm.is_active = true
                """
                recipients_raw = await session.execute(
                    recipients_query, (connector_contact_type_id.id, chat_id)
                )
                recipients_ids = [
                    {"id": r["id"], "contact_value": r["contact_value"]}
                    for r in recipients_raw
                ]

            await connector.strategy.send_outgoing_message(
                env,
                chat_id=chat_id,
                connector_id=connector,
                user_id=user_id,
                body=body.body,
                message_id=message.id,
                attachments=attachments_content_data,
                recipients_ids=recipients_ids,
            )

        # Отправляем через WebSocket
        await chat_manager.send_to_chat(
            chat_id=chat_id,
            message={
                "type": "new_message",
                "chat_id": chat_id,
                "message": {
                    "id": message.id,
                    "body": message.body,
                    "message_type": "comment",
                    "author": {
                        "id": user_id,
                        "name": auth_session.user_id.name,
                        "type": "user",
                    },
                    "create_date": (
                        message.create_date.isoformat()
                        if message.create_date
                        else None
                    ),
                    "starred": False,
                    "pinned": False,
                    "is_edited": False,
                    "is_read": False,
                    "attachments": attachments_response,
                },
            },
            exclude_user=user_id,
        )

        # Отправляем через Web Push
        # Отправляем push-уведомления через notify-коннекторы
        try:
            await notify_on_new_message(
                chat_id=chat_id,
                message_id=message.id,
                author_user_id=auth_session.user_id,
                body=body.body,
                exclude_user_id=user_id,
            )
        except Exception as notify_err:
            import logging

            logging.getLogger(__name__).error(
                "[notify] Failed: %s", notify_err, exc_info=True
            )

    return {
        "data": {
            "id": message.id,
            "body": message.body,
            "create_date": (
                message.create_date.isoformat()
                if message.create_date
                else None
            ),
            "attachments": attachments_response,
        }
    }


@router_private.delete("/chats/{chat_id}/messages/{message_id}")
async def delete_message(req: Request, chat_id: int, message_id: int):
    """
    Удалить сообщение.
    Можно удалять свои сообщения или чужие с правом can_delete_others.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство
    member = await ChatMember.check_membership(chat_id, user_id)
    message = await env.models.chat_message.get(
        message_id,
        fields=["author_user_id"],
        fields_nested={"author_user_id": ["id"]},
    )

    # Проверяем права: своё сообщение, can_delete_others или админ чата.
    # Глобальный is_admin тоже проходит (single source of truth — роутер).
    is_own_message = (
        message.author_user_id and message.author_user_id.id == user_id
    )
    is_chat_admin = member.is_admin or auth_session.user_id.is_admin
    if (
        not is_own_message
        and not is_chat_admin
        and not member.has_permission("can_delete_others")
    ):
        raise FaraException(
            {
                "content": "PERMISSION_DENIED",
                "detail": "Cannot delete other's messages",
                "status_code": HTTP_403_FORBIDDEN,
            }
        )

    # Soft delete
    await message.update(env.models.chat_message(is_deleted=True))

    # Уведомляем через WebSocket
    await chat_manager.send_to_chat(
        chat_id=chat_id,
        message={
            "type": "message_deleted",
            "chat_id": chat_id,
            "message_id": message_id,
        },
    )

    return {"success": True}


@router_private.patch("/chats/{chat_id}/messages/{message_id}")
async def edit_message(
    req: Request, chat_id: int, message_id: int, body: MessageEdit
):
    """
    Редактировать сообщение (только своё).
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство и сразу получаем member (нужен is_admin ниже)
    member = await ChatMember.check_membership(chat_id, user_id)

    message = await env.models.chat_message.get(
        message_id,
        fields=["author_user_id"],
        fields_nested={"author_user_id": ["id"]},
    )

    # Редактировать сообщение может автор или админ чата.
    # Глобальный is_admin байпасит проверки прав на уровне ORM,
    # но здесь мы в императивной ветке — учитываем его явно.
    is_author = message.author_user_id and message.author_user_id.id == user_id
    is_chat_admin = member.is_admin or auth_session.user_id.is_admin
    if not is_author and not is_chat_admin:
        raise FaraException(
            {
                "content": "PERMISSION_DENIED",
                "detail": "Can only edit own messages",
                "status_code": HTTP_403_FORBIDDEN,
            }
        )

    await message.update(
        env.models.chat_message(body=body.body, is_edited=True)
    )

    # Уведомляем через WebSocket
    await chat_manager.send_to_chat(
        chat_id=chat_id,
        message={
            "type": "message_edited",
            "chat_id": chat_id,
            "message_id": message_id,
            "body": body.body,
        },
    )

    return {"success": True}


@router_private.post("/chats/{chat_id}/messages/{message_id}/pin")
async def pin_message(
    req: Request, chat_id: int, message_id: int, body: MessagePin
):
    """
    Закрепить/открепить сообщение.
    Требует права can_pin.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем право на закрепление
    await ChatMember.check_can_pin(chat_id, user_id)

    message = await env.models.chat_message.get(message_id)

    await message.update(env.models.chat_message(pinned=body.pinned))

    # Уведомляем через WebSocket
    await chat_manager.send_to_chat(
        chat_id=chat_id,
        message={
            "type": "message_pinned",
            "chat_id": chat_id,
            "message_id": message_id,
            "pinned": body.pinned,
        },
    )

    return {"success": True, "pinned": body.pinned}


@router_private.post("/chats/{chat_id}/read")
async def mark_as_read(req: Request, chat_id: int):
    """
    Отметить все сообщения чата как прочитанные для текущего пользователя.

    Двигает watermark (chat_member.last_read_message_id) до id самого
    последнего сообщения в чате. Одна операция обновления одной строки —
    не трогает chat_message вообще.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    member = await ChatMember.check_membership(chat_id, user_id)

    # Берём id самого последнего сообщения в чате
    latest = await env.models.chat_message.search(
        filter=[
            ("chat_id", "=", chat_id),
            ("is_deleted", "=", False),
        ],
        fields=["id"],
        sort="id",
        order="DESC",
        limit=1,
    )
    if not latest:
        return {"success": True, "count": 0}

    latest_id = latest[0].id
    current_watermark = member.last_read_message_id or 0
    if latest_id <= current_watermark:
        return {"success": True, "count": 0}

    await member.update(env.models.chat_member(last_read_message_id=latest_id))

    # Уведомляем через WebSocket — остальные участники увидят, что
    # этот user прочитал чат (для будущих UX-индикаторов).
    await chat_manager.send_to_chat(
        chat_id=chat_id,
        message={
            "type": "messages_read",
            "chat_id": chat_id,
            "user_id": user_id,
            "last_read_message_id": latest_id,
        },
    )

    return {"success": True, "count": latest_id - current_watermark}


@router_private.post("/chats/{chat_id}/messages/{message_id}/unread")
async def mark_as_unread(req: Request, chat_id: int, message_id: int):
    """
    Отметить сообщения начиная с указанного как непрочитанные.

    Откатывает watermark к (message_id - 1): всё начиная с message_id
    включительно снова считается непрочитанным.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    member = await ChatMember.check_membership(chat_id, user_id)

    new_watermark = max(0, message_id - 1)
    await member.update(
        env.models.chat_member(last_read_message_id=new_watermark)
    )

    return {"success": True}


@router_private.get("/chats/{chat_id}/pinned")
async def get_pinned_messages(req: Request, chat_id: int):
    """
    Получить закрепленные сообщения чата.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство
    await ChatMember.check_membership(chat_id, user_id)

    messages = await env.models.chat_message.get_pinned_messages(
        chat_id=chat_id
    )

    result = []
    for msg in messages:
        result.append(
            {
                "id": msg.id,
                "body": msg.body,
                "message_type": msg.message_type,
                "create_date": msg.create_date.isoformat(),
                "author": format_message_author(msg),
            }
        )

    return {"data": result}


@router_private.post("/chats/{chat_id}/messages/{message_id}/reactions")
async def add_reaction(
    req: Request, chat_id: int, message_id: int, body: MessageReaction
):
    """
    Добавить реакцию к сообщению.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство
    await ChatMember.check_membership(chat_id, user_id)

    message = await env.models.chat_message.get(message_id)

    # Проверяем, есть ли уже такая реакция от этого пользователя
    existing = await env.models.chat_message_reaction.search(
        filter=[
            ("message_id", "=", message_id),
            ("user_id", "=", user_id),
            ("emoji", "=", body.emoji),
        ],
        fields=["id"],
    )

    if existing:
        # Удаляем реакцию (toggle)
        await existing[0].delete()
        action = "removed"
    else:
        # Добавляем реакцию
        reaction = env.models.chat_message_reaction(
            emoji=body.emoji,
            message_id=message,
            user_id=auth_session.user_id,
        )
        await env.models.chat_message_reaction.create(reaction)
        action = "added"

    # Получаем все реакции для сообщения
    reactions = await get_message_reactions(env, message_id)

    # Уведомляем через WebSocket
    await chat_manager.send_to_chat(
        chat_id=chat_id,
        message={
            "type": "reaction_changed",
            "chat_id": chat_id,
            "message_id": message_id,
            "reactions": reactions,
        },
    )

    return {"success": True, "action": action, "reactions": reactions}


@router_private.get("/chats/{chat_id}/messages/{message_id}/reactions")
async def get_reactions(req: Request, chat_id: int, message_id: int):
    """
    Получить реакции к сообщению.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство
    await ChatMember.check_membership(chat_id, user_id)

    reactions = await get_message_reactions(env, message_id)
    return {"data": reactions}


async def get_message_reactions(
    env: "Environment", message_id: int
) -> list[dict]:
    """Вспомогательная функция для получения реакций сообщения."""
    reactions_raw = await env.models.chat_message_reaction.search(
        filter=[("message_id", "=", message_id)],
        fields=["id", "emoji", "user_id"],
    )

    # Группируем по эмодзи
    reactions_map: dict[str, list] = {}
    for r in reactions_raw:
        emoji = r.emoji
        if emoji not in reactions_map:
            reactions_map[emoji] = []
        reactions_map[emoji].append(
            {
                "user_id": r.user_id.id,
                "user_name": r.user_id.name,
            }
        )

    return [
        {"emoji": emoji, "users": users, "count": len(users)}
        for emoji, users in reactions_map.items()
    ]


@router_private.post("/chats/{chat_id}/messages/{message_id}/forward")
async def forward_message(
    req: Request, chat_id: int, message_id: int, body: MessageForward
):
    """
    Переслать сообщение в другой чат.
    Требует can_write в целевом чате.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем доступ к исходному чату
    await ChatMember.check_membership(chat_id, user_id)

    # Проверяем право писать в целевой чат
    await ChatMember.check_can_write(body.target_chat_id, user_id)

    original_message = await env.models.chat_message.get(message_id)

    # Определяем автора оригинального сообщения
    if original_message.author_user_id:
        original_author_name = original_message.author_user_id.name
    elif original_message.author_partner_id:
        original_author_name = original_message.author_partner_id.name
    else:
        original_author_name = "Unknown"

    # Создаём новое сообщение в целевом чате
    forwarded_body = (
        f"[Forwarded from {original_author_name}]\n{original_message.body}"
    )

    new_message = await env.models.chat_message.post_message(
        chat_id=body.target_chat_id,
        author_user_id=user_id,
        body=forwarded_body,
    )

    # Уведомляем через WebSocket
    await chat_manager.send_to_chat(
        chat_id=body.target_chat_id,
        message={
            "type": "new_message",
            "chat_id": body.target_chat_id,
            "message": {
                "id": new_message.id,
                "body": forwarded_body,
                "message_type": "comment",
                "author": {
                    "id": user_id,
                    "name": auth_session.user_id.name,
                    "type": "user",
                },
                "create_date": (
                    new_message.create_date.isoformat()
                    if new_message.create_date
                    else None
                ),
                "starred": False,
                "pinned": False,
                "is_edited": False,
                "is_read": False,
            },
        },
        exclude_user=user_id,
    )

    return {"success": True, "message_id": new_message.id}
