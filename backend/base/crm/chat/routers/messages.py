# Copyright 2025 FARA CRM
# Chat module - messages router

import logging
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request, Query
from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from backend.base.crm.auth_token.app import AuthTokenApp
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

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session

router_private = APIRouter(
    tags=["Chat"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


async def _chat_message(
    env: "Environment", chat_id: int, message_id: int, fields: list[str]
):
    """Сообщение ЭТОГО чата. Права проверяются в чате из адреса, поэтому
    сообщение другого чата по этому адресу не найти — 404."""
    message = await env.models.chat_message.search_one(
        filter=[("id", "=", message_id), ("chat_id", "=", chat_id)],
        fields=fields,
    )
    if not message:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )
    return message


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

    # Читают участники, а без членства — команда чата и суперпользователь
    # (правила доступа chat). Так «Все» реально открывается и читается
    # не-членом команды (писать — вступив).
    current_member = await ChatMember.get_membership(chat_id, user_id)
    if not current_member:
        await env.models.chat.check_read_access(chat_id)

    # Soft-delete: показывать удалённые только админам
    _is_admin = auth_session.user_id.is_admin or bool(
        current_member and current_member.is_admin
    )
    _show_deleted = bool(include_deleted) and _is_admin

    messages = await env.models.chat_message.get_chat_messages(
        chat_id=chat_id,
        limit=limit,
        before_id=before_id,
        include_deleted=_show_deleted,
    )

    # Watermark есть только у участника; у остальных всё непрочитано.
    last_read_watermark = 0
    if current_member:
        last_read_watermark = current_member.last_read_message_id or 0

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
            attachments_by_message[msg_id].append(att.serialize_for_chat())

    # Реакции для всех сообщений одним запросом
    reactions_by_message = (
        await env.models.chat_message_reaction.grouped(message_ids)
        if message_ids
        else {}
    )

    result = []
    for msg in messages:
        # is_read вычисляется из watermark: сообщение прочитано, если его
        # id <= last_read_watermark. Своё сообщение всегда считаем
        # прочитанным (автор его видел, ведь он его написал).
        is_own = msg.author_user_id and msg.author_user_id.id == user_id
        computed_is_read = is_own or (msg.id <= last_read_watermark)
        result.append(
            msg.serialize_for_chat(
                is_read=computed_is_read,
                attachments=attachments_by_message.get(msg.id, []),
                reactions=reactions_by_message.get(msg.id, []),
            )
        )

    # Архитектура 2: звонки — независимая сущность (таблица call), в истории
    # чата они подмешиваются на чтении как виртуальные сообщения call_external
    # (по времени). Окно выравниваем по самому старому сообщению страницы; если
    # страница неполная — берём последние звонки без нижней границы. messages
    # отсортированы id DESC, поэтому messages[-1] — самое старое сообщение.
    time_from = None
    if messages and len(messages) >= limit:
        oldest = messages[-1].create_datetime
        time_from = oldest.isoformat() if oldest else None
    calls = await env.models.call.list_for_chat(
        env, chat_id, time_from=time_from, limit=limit
    )
    result.extend(calls)

    return {"data": result}


@router_private.get("/chats/{chat_id}/messages/search")
async def search_messages(
    req: Request,
    chat_id: int,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Поиск сообщений чата по тексту (лупа в шапке). Доступ — как у ленты:
    член / админ / team-читатель, иначе 403. Ответ — список совпадений
    (новые первыми) в формате закреплённых, без вложений и реакций.
    """
    env: "Environment" = req.app.state.env
    await env.models.chat.check_read_access(chat_id)

    messages = await env.models.chat_message.search_chat_messages(
        chat_id=chat_id, query=q.strip(), limit=limit
    )
    return {"data": [msg.serialize_for_list() for msg in messages]}


@router_private.get("/chats/messages/count")
async def get_messages_count(
    req: Request,
    res_model: str = Query(
        ..., description="Модель записи (partner, lead, ...)"
    ),
    res_id: int = Query(..., description="ID записи"),
):
    """
    Статистика по сообщениям в record-чате записи `res_model`/`res_id`.

    Ответ:
        {
            "total": N,   // всего не удалённых сообщений в чате
            "unread": N   // непрочитанных для текущего пользователя
        }

    unread считается так:
    - 0 если record-чата ещё нет (никто не подписался),
    - 0 если пользователь не член чата (не подписан),
    - иначе COUNT(*) сообщений с id > last_read_message_id пользователя,
      не считая своих (author_user_id != me).

    Такой же SQL-паттерн используется в GET /chats (watermark-based unread).

    Безопасность: отдаём только числа. Доступ к записи (res_model/res_id)
    уже проверен Rules-ами соответствующей модели.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Если record-чата ещё нет — ни total, ни unread смысла не имеют.
    chat_record = await env.models.chat.search_one(
        filter=[
            ("res_model", "=", res_model),
            ("res_id", "=", res_id),
            ("chat_type", "=", "record"),
            ("active", "=", True),
        ],
        fields=["id"],
    )
    if not chat_record:
        return {"total": 0, "unread": 0}

    chat_id = chat_record.id

    total = await env.models.chat_message.search_count(
        filter=[
            ("chat_id", "=", chat_id),
            ("is_deleted", "=", False),
        ]
    )

    # Непрочитанные — по watermark участника, как в списке чатов. У не
    # подписанного на чат их нет: строка не вернётся.
    unread_rows = await env.models.chat_message.unread_counts(
        user_id, [chat_id]
    )
    unread = unread_rows[0]["unread_count"] if unread_rows else 0

    return {"total": total, "unread": unread}


@router_private.get("/records/{res_model}/{res_id}/partner_chat")
async def resolve_record_partner_chat(
    req: Request, res_model: str, res_id: int
):
    """Внешний чат ПАРТНЁРА записи (модель 1:1) — БЕЗ создания (не плодим
    пустой чат на открытие панели). Партнёр записи: для partners — сама
    запись, иначе поле partner_id записи (лид, заказ — любая модель с таким
    полем); доступ к записи проверяют штатные правила её модели (ORM search).
    Возвращает {chat_id|null, partner_id|null}. Содержимое чата читается
    штатным GET /chats/{id}/messages (там и применяется доступ: членство/
    team-правило). Тот же partner_id использует панель «Звонки».
    """
    env: "Environment" = req.app.state.env
    partner_id = await _record_partner_id(env, res_model, res_id)
    if not partner_id:
        return {"chat_id": None, "partner_id": None}
    chat = await env.models.chat.find_partner_group_chat(partner_id)
    return {"chat_id": chat.id if chat else None, "partner_id": partner_id}


async def _record_partner_id(
    env: "Environment", res_model: str, res_id: int
) -> int | None:
    """Партнёр записи res_model/res_id (res_model — имя таблицы, как на фронте)."""
    if res_model == "partners":
        return res_id
    try:
        Model = env.models._get_model_class_by_table(res_model)
    except KeyError:
        return None
    if "partner_id" not in Model.get_fields():
        return None
    record = await Model.search_one(
        filter=[("id", "=", res_id)], fields=["id", "partner_id"]
    )
    return record.partner_id.id if record and record.partner_id else None


@router_private.post("/partners/{partner_id}/chat")
async def create_partner_chat(req: Request, partner_id: int):
    """Создать (или вернуть существующий) ГРУППОВОЙ клиентский чат партнёра —
    кнопка «Создать чат» в панели, когда чата ещё нет. Партнёр добавляется
    участником внутри get_or_create_partner_chat; текущего пользователя
    подписываем отдельно (чтобы он мог писать). connector=None → без команды/
    руководителей (ручное создание из карточки)."""
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    chat = await env.models.chat.get_or_create_partner_chat(partner_id)
    await chat._ensure_membership(chat.id, user_id)
    return {"chat_id": chat.id, "partner_id": partner_id}


@router_private.get("/chats/{chat_id}/tags")
async def get_chat_tags(
    req: Request,
    chat_id: int,
    limit: int = Query(5, ge=1, le=20, description="Сколько последних тегов"),
):
    """Недавние теги чата — для селектора тега в панели ленты.

    Собирает distinct лиды/задачи, засветившиеся в сообщениях чата,
    отсортированные по времени (MAX(id) DESC — id монотонен, дешевле
    create_datetime). Доступ гейтится через chat.get() (правила @is_member /
    team-доступ применяются на ORM-пути; не видишь чат — RecordNotFound).
    """
    env: "Environment" = req.app.state.env

    # Гейт доступа: если чат не виден пользователю — get() бросит/пусто.
    await env.models.chat.get(chat_id, fields=["id"])

    session = env.apps.db.get_session()
    lead_rows = await session.execute(
        """
        SELECT lead_id, MAX(id) AS last
        FROM chat_message
        WHERE chat_id = %s AND lead_id IS NOT NULL AND is_deleted = false
        GROUP BY lead_id
        ORDER BY last DESC
        LIMIT %s
        """,
        (chat_id, limit),
    )
    task_rows = await session.execute(
        """
        SELECT task_id, MAX(id) AS last
        FROM chat_message
        WHERE chat_id = %s AND task_id IS NOT NULL AND is_deleted = false
        GROUP BY task_id
        ORDER BY last DESC
        LIMIT %s
        """,
        (chat_id, limit),
    )
    return {
        "data": {
            "lead_ids": [r["lead_id"] for r in lead_rows],
            "task_ids": [r["task_id"] for r in task_rows],
        }
    }


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
    member = await ChatMember.check_membership(chat_id, user_id)
    member.require(member.can_write)

    message, attachments = await env.models.chat_message.send(
        chat_id=chat_id,
        author=auth_session.user_id,
        body=body.body,
        files=body.attachments,
        connector_id=body.connector_id,
        parent_id=body.parent_id,
        lead_id=body.lead_id,
        task_id=body.task_id,
    )

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
        log.error("[notify] Failed: %s", notify_err, exc_info=True)

    return {
        "data": {
            "id": message.id,
            "body": message.body,
            "create_datetime": (
                message.create_datetime.isoformat()
                if message.create_datetime
                else None
            ),
            "attachments": attachments,
            "send_failed": message.send_failed is True,
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
    message = await _chat_message(
        env, chat_id, message_id, fields=["id", "author_user_id"]
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
        and not member.can_delete_others
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
    await env.apps.chat.chat_manager.send_to_chat(
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

    message = await _chat_message(
        env, chat_id, message_id, fields=["id", "author_user_id"]
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
    await env.apps.chat.chat_manager.send_to_chat(
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
    member = await ChatMember.check_membership(chat_id, user_id)
    member.require(member.can_pin)

    message = await _chat_message(env, chat_id, message_id, fields=["id"])

    await message.update(env.models.chat_message(pinned=body.pinned))

    # Уведомляем через WebSocket
    await env.apps.chat.chat_manager.send_to_chat(
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
    latest = await env.models.chat_message.search_one(
        filter=[
            ("chat_id", "=", chat_id),
            ("is_deleted", "=", False),
        ],
        fields=["id"],
        sort="id",
        order="DESC",
    )
    if not latest:
        return {"success": True, "count": 0}

    latest_id = latest.id
    current_watermark = member.last_read_message_id or 0
    if latest_id <= current_watermark:
        return {"success": True, "count": 0}

    await member.update(env.models.chat_member(last_read_message_id=latest_id))

    # Уведомляем через WebSocket — остальные участники увидят, что
    # этот user прочитал чат (для будущих UX-индикаторов).
    await env.apps.chat.chat_manager.send_to_chat(
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

    # Проверка членства реализована через rule "@is_member" на chat_message:
    # search вернёт пустой список для не-участников.
    messages = await env.models.chat_message.get_pinned_messages(
        chat_id=chat_id
    )

    return {"data": [msg.serialize_for_list() for msg in messages]}


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

    message = await _chat_message(env, chat_id, message_id, fields=["id"])

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
    await env.apps.chat.chat_manager.send_to_chat(
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

    # Проверка реализована через rule "@has_parent_access" на chat_message_reaction:
    # search вернёт пустой список если у юзера нет доступа к сообщению.
    reactions = await get_message_reactions(env, message_id)
    return {"data": reactions}


async def get_message_reactions(
    env: "Environment", message_id: int
) -> list[dict]:
    """Вспомогательная функция для получения реакций сообщения."""
    grouped = await env.models.chat_message_reaction.grouped([message_id])
    return grouped.get(message_id, [])


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

    # Источник forward — READ: кто читает чат, тот и пересылает из него
    await env.models.chat.check_read_access(chat_id)

    # Проверяем право писать в целевой чат
    target_member = await ChatMember.check_membership(
        body.target_chat_id, user_id
    )
    target_member.require(target_member.can_write)

    original_message = await _chat_message(
        env,
        chat_id,
        message_id,
        fields=["id", "body", "author_user_id", "author_partner_id"],
    )

    # Создаём новое сообщение в целевом чате
    forwarded_body = (
        f"[Forwarded from {original_message.author['name']}]\n"
        f"{original_message.body}"
    )

    new_message = await env.models.chat_message.post_message(
        chat_id=body.target_chat_id,
        author_user_id=user_id,
        body=forwarded_body,
    )

    # Уведомляем через WebSocket
    await env.apps.chat.chat_manager.send_to_chat(
        chat_id=body.target_chat_id,
        message={
            "type": "new_message",
            "chat_id": body.target_chat_id,
            "message": new_message.serialize_for_ws(
                author={
                    "id": user_id,
                    "name": auth_session.user_id.name,
                    "type": "user",
                },
                attachments=[],
            ),
        },
        exclude_user=user_id,
    )

    return {"success": True, "message_id": new_message.id}
