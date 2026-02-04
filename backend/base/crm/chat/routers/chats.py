# Copyright 2025 FARA CRM
# Chat module - chats router

import asyncio
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request, Query
from starlette.status import HTTP_404_NOT_FOUND, HTTP_403_FORBIDDEN

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException
from ..schemas.chat import ChatCreate, ChatUpdate, AddMemberInput
from ..models.chat_member import ChatMember

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session

router_private = APIRouter(
    tags=["Chat"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


@router_private.get("/chats")
async def get_chats(
    req: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_internal: bool | None = Query(
        None, description="Фильтр: True=внутренние, False=внешние, None=все"
    ),
    chat_type: str | None = Query(
        None, description="Фильтр по типу: direct, group"
    ),
    connector_type: str | None = Query(
        None, description="Фильтр по коннектору: telegram, whatsapp, etc"
    ),
):
    """
    Получить список чатов текущего пользователя.

    Комбо-фильтрация:
    - is_internal=True + chat_type=direct → Внутренние личные
    - is_internal=True + chat_type=group → Внутренние группы
    - is_internal=False + connector_type=telegram → Telegram чаты
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    session = env.apps.db.get_session()

    # Строим SQL динамически
    base_query = """
        SELECT DISTINCT c.id, c.last_message_date
        FROM chat c
        JOIN chat_member cm ON c.id = cm.chat_id AND cm.is_active = true
    """

    conditions = ["cm.user_id = %s", "c.active = true"]
    params: list = [user_id]

    # Фильтр is_internal
    if is_internal is True:
        conditions.append("c.is_internal = true")
    elif is_internal is False:
        conditions.append("c.is_internal = false")

    # Фильтр chat_type
    if chat_type:
        if chat_type == "group":
            conditions.append("c.chat_type IN ('group', 'channel')")
        else:
            conditions.append("c.chat_type = %s")
            params.append(chat_type)

    # Фильтр connector_type — через контакты партнёров-участников чата.
    # Логика: connector.contact_type_id → contact.contact_type_id → partner → chat_member.
    # Ищем чаты где у партнёра есть контакт с тем же contact_type_id что у коннектора.
    if connector_type:
        # Получаем contact_type_id из коннектора (integer FK)
        contact_type_id_for_filter = (
            await env.models.contact_type.get_contact_type_id_for_connector(
                connector_type
            )
        )

        if contact_type_id_for_filter:
            base_query += """
            JOIN chat_member cm_filter ON c.id = cm_filter.chat_id 
                AND cm_filter.partner_id IS NOT NULL AND cm_filter.is_active = true
            JOIN contact contact_filter ON contact_filter.partner_id = cm_filter.partner_id 
                AND contact_filter.active = true
                AND contact_filter.contact_type_id = %s
            """
            params.insert(0, contact_type_id_for_filter.id)

    where_clause = " AND ".join(conditions)
    chat_ids_query = f"""
        {base_query}
        WHERE {where_clause}
        ORDER BY c.last_message_date DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    all_params = params + [limit, offset]

    chat_id_rows = await session.execute(chat_ids_query, tuple(all_params))

    if not chat_id_rows:
        return {"data": [], "total": 0}

    chat_ids = [row["id"] for row in chat_id_rows]

    # Шаг 2: Параллельно загружаем все данные
    chats_task = env.models.chat.search(
        filter=[("id", "in", chat_ids)],
        fields=[
            "id",
            "name",
            "chat_type",
            "last_message_date",
            "create_date",
        ],
        limit=limit,
    )

    # Получаем участников (пользователей и партнёров) через chat_member
    members_query = """
        SELECT cm.chat_id, 
               COALESCE(u.id, p.id) as id,
               COALESCE(u.name, p.name) as name, 
               COALESCE(u.email, p.email) as email,
               CASE WHEN cm.user_id IS NOT NULL THEN 'user' ELSE 'partner' END as member_type,
               cm.can_read,
               cm.can_write,
               cm.can_invite,
               cm.can_pin,
               cm.can_delete_others,
               cm.is_admin
        FROM chat_member cm
        LEFT JOIN users u ON u.id = cm.user_id
        LEFT JOIN partners p ON p.id = cm.partner_id
        WHERE cm.chat_id = ANY(%s) AND cm.is_active = true
    """
    members_task = session.execute(members_query, (chat_ids,))

    last_messages_query = """
        SELECT DISTINCT ON (chat_id) 
            id, chat_id, body, message_type, author_user_id, author_partner_id, create_date
        FROM chat_message
        WHERE chat_id = ANY(%s) AND is_deleted = false
        ORDER BY chat_id, id DESC
    """
    last_messages_task = session.execute(last_messages_query, (chat_ids,))

    unread_query = """
        SELECT chat_id, COUNT(*) as unread_count
        FROM chat_message
        WHERE chat_id = ANY(%s) 
          AND (author_user_id IS NULL OR author_user_id != %s)
          AND is_read = false 
          AND is_deleted = false
        GROUP BY chat_id
    """
    unread_task = session.execute(unread_query, (chat_ids, user_id))

    # Запрос информации о коннекторах
    # Новая логика: получаем коннекторы на основе контактов партнёров-участников чата
    # Маппинг contact → connector через общий contact_type_id (integer FK)
    # contact.contact_type_id = chat_connector.contact_type_id
    connectors_query = """
        SELECT DISTINCT 
            cm.chat_id,
            cc.id as connector_id,
            cc.type as connector_type,
            cc.name as connector_name,
            c.id as contact_id,
            c.name as contact_value
        FROM chat_member cm
        JOIN contact c ON c.partner_id = cm.partner_id AND c.active = true
        JOIN chat_connector cc ON cc.active = true 
            AND cc.contact_type_id = c.contact_type_id
        WHERE cm.chat_id = ANY(%s) 
          AND cm.partner_id IS NOT NULL 
          AND cm.is_active = true
    """
    connectors_task = session.execute(connectors_query, (chat_ids,))

    # Выполняем параллельно (каждый запрос в своём соединении из пула)
    chats_orm, members_raw, last_messages_raw, unread_raw, connectors_raw = (
        await asyncio.gather(
            chats_task,
            members_task,
            last_messages_task,
            unread_task,
            connectors_task,
        )
    )

    # Индексируем чаты для сохранения порядка сортировки
    chats_by_id = {c.id: c for c in chats_orm}
    chats_sorted = [chats_by_id[cid] for cid in chat_ids if cid in chats_by_id]

    # Группируем участников по chat_id
    members_by_chat: dict[int, list] = {}
    for m in members_raw:
        cid = m["chat_id"]
        if cid not in members_by_chat:
            members_by_chat[cid] = []
        members_by_chat[cid].append(
            {
                "id": m["id"],
                "name": m["name"],
                "email": m["email"],
                "member_type": m["member_type"],
                "permissions": {
                    "can_read": m["can_read"],
                    "can_write": m["can_write"],
                    "can_invite": m["can_invite"],
                    "can_pin": m["can_pin"],
                    "can_delete_others": m["can_delete_others"],
                    "is_admin": m["is_admin"],
                },
            }
        )

    # Группируем последние сообщения и собираем author_user_ids и partner_ids
    last_message_by_chat: dict[int, dict] = {}
    author_user_ids = set()
    author_partner_ids = set()
    for msg in last_messages_raw:
        last_message_by_chat[msg["chat_id"]] = msg
        if msg["author_user_id"]:
            author_user_ids.add(msg["author_user_id"])
        if msg.get("author_partner_id"):
            author_partner_ids.add(msg["author_partner_id"])

    # Шаг 3: Загружаем имена авторов (users и partners)
    author_names: dict[int, str] = {}
    partner_names: dict[int, str] = {}

    if author_user_ids:
        authors_query = "SELECT id, name FROM users WHERE id = ANY(%s)"
        authors_raw = await session.execute(
            authors_query, (list(author_user_ids),)
        )
        for author in authors_raw:
            author_names[author["id"]] = author["name"]

    if author_partner_ids:
        partners_query = "SELECT id, name FROM partners WHERE id = ANY(%s)"
        partners_raw = await session.execute(
            partners_query, (list(author_partner_ids),)
        )
        for partner in partners_raw:
            partner_names[partner["id"]] = partner["name"]

    # Группируем непрочитанные
    unread_by_chat: dict[int, int] = {
        row["chat_id"]: row["unread_count"] for row in unread_raw
    }

    # Группируем коннекторы по chat_id (список)
    connectors_by_chat: dict[int, list] = {}
    for conn in connectors_raw:
        cid = conn["chat_id"]
        if cid not in connectors_by_chat:
            connectors_by_chat[cid] = []
        connectors_by_chat[cid].append(
            {
                "id": conn["connector_id"],
                "type": conn["connector_type"],
                "name": conn["connector_name"],
                "contact_id": conn.get("contact_id"),
                "contact_value": conn.get("contact_value"),
            }
        )

    # Формируем результат
    result = []
    for chat in chats_sorted:
        chat_data = {
            "id": chat.id,
            "name": chat.name,
            "chat_type": chat.chat_type,
            "is_internal": chat.is_internal,
            "connectors": connectors_by_chat.get(chat.id, []),
            "last_message_date": (
                chat.last_message_date.isoformat()
                if chat.last_message_date
                else None
            ),
            "create_date": (
                chat.create_date.isoformat() if chat.create_date else None
            ),
            "unread_count": unread_by_chat.get(chat.id, 0),
            "members": members_by_chat.get(chat.id, []),
        }

        last_msg = last_message_by_chat.get(chat.id)
        if last_msg:
            # Определяем автора: user или partner
            author_user_id = last_msg["author_user_id"]
            author_partner_id = last_msg.get("author_partner_id")

            author_name = None
            if author_user_id:
                author_name = author_names.get(author_user_id)
            elif author_partner_id:
                author_name = partner_names.get(author_partner_id)

            chat_data["last_message"] = {
                "id": last_msg["id"],
                "body": last_msg["body"],
                "message_type": last_msg.get("message_type", "comment"),
                "author_id": author_user_id or author_partner_id,
                "author_name": author_name,
                "create_date": (
                    last_msg["create_date"].isoformat()
                    if last_msg["create_date"]
                    else None
                ),
            }
        else:
            chat_data["last_message"] = None

        result.append(chat_data)

    return {"data": result, "total": len(result)}


@router_private.get("/chats/{chat_id}")
async def get_chat(req: Request, chat_id: int):
    """
    Получить информацию о чате.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    session = env.apps.db.get_session()

    # Проверяем членство (бросит исключение если не участник)
    await ChatMember.check_membership(chat_id, user_id)

    try:
        chat = await env.models.chat.get(chat_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    # Получаем участников отдельным запросом

    members_query = """
        SELECT 
            COALESCE(u.id, p.id) as id,
            COALESCE(u.name, p.name) as name,
            COALESCE(u.email, p.email) as email,
            CASE WHEN cm.user_id IS NOT NULL THEN 'user' ELSE 'partner' END as member_type,
            cm.can_read,
            cm.can_write,
            cm.can_invite,
            cm.can_pin,
            cm.can_delete_others,
            cm.is_admin
        FROM chat_member cm
        LEFT JOIN users u ON u.id = cm.user_id
        LEFT JOIN partners p ON p.id = cm.partner_id
        WHERE cm.chat_id = %s AND cm.is_active = true
    """
    members_raw = await session.execute(members_query, (chat_id,))
    members = [
        {
            "id": m["id"],
            "name": m["name"],
            "email": m["email"],
            "member_type": m["member_type"],
            "permissions": {
                "can_read": m["can_read"],
                "can_write": m["can_write"],
                "can_invite": m["can_invite"],
                "can_pin": m["can_pin"],
                "can_delete_others": m["can_delete_others"],
                "is_admin": m["is_admin"],
            },
        }
        for m in members_raw
    ]

    return {
        "data": {
            "id": chat.id,
            "name": chat.name,
            "chat_type": chat.chat_type,
            "description": chat.description,
            "is_internal": chat.is_internal,
            "is_public": chat.is_public,
            "create_date": (
                chat.create_date.isoformat() if chat.create_date else None
            ),
            "members": members,
            # Default permissions
            "default_can_read": getattr(chat, "default_can_read", True),
            "default_can_write": getattr(chat, "default_can_write", True),
            "default_can_invite": getattr(chat, "default_can_invite", False),
            "default_can_pin": getattr(chat, "default_can_pin", False),
            "default_can_delete_others": getattr(
                chat, "default_can_delete_others", False
            ),
        }
    }


@router_private.post("/chats")
async def create_chat(req: Request, body: ChatCreate):
    """
    Создать новый чат.

    Поддерживает создание:
    - Внутренних чатов между пользователями (user_ids)
    - Внешних чатов с партнёрами (partner_ids)
    - Смешанных групповых чатов
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Определяем тип чата: внутренний или внешний
    has_partners = len(body.partner_ids) > 0
    has_users = len(body.user_ids) > 0

    async with env.apps.db.get_transaction():
        if body.chat_type == "direct":
            # Для direct чата нужен ровно один собеседник
            total_recipients = len(body.user_ids) + len(body.partner_ids)
            if total_recipients != 1:
                raise FaraException(
                    {"content": "DIRECT_CHAT_REQUIRES_ONE_RECIPIENT"}
                )

            if has_partners:
                # Создаём внешний чат с партнёром
                partner_id = body.partner_ids[0]
                partner = await env.models.partner.get(partner_id)
                if not partner:
                    raise FaraException({"content": "PARTNER_NOT_FOUND"})

                chat = await env.models.chat.create_partner_chat(
                    user_id=user_id,
                    partner_id=partner_id,
                    chat_name=partner.name,
                )
                all_user_ids = [user_id]
                is_internal = False
            else:
                # Создаём внутренний чат между пользователями
                chat = await env.models.chat.create_direct_chat(
                    user1_id=user_id, user2_id=body.user_ids[0]
                )
                all_user_ids = [user_id, body.user_ids[0]]
                is_internal = True
        else:
            # Групповой чат
            if not body.name:
                raise FaraException({"content": "NAME_REQUIRED"})

            chat = await env.models.chat.create_group_chat(
                name=body.name,
                creator_id=user_id,
                member_ids=body.user_ids,
            )
            all_user_ids = [user_id] + [
                m for m in body.user_ids if m != user_id
            ]

            # Добавляем партнёров в групповой чат
            if has_partners:
                for partner_id in body.partner_ids:
                    await chat.add_partner(partner_id)
                is_internal = False
            else:
                is_internal = True

    # Уведомляем всех участников о новом чате через WebSocket
    from ..websocket import chat_manager

    chat_data = {
        "id": chat.id,
        "name": chat.name,
        "chat_type": chat.chat_type,
        "is_internal": is_internal,
        "members": [],  # Будет заполнено на клиенте при refetch
        "unread_count": 0,
        "connectors": [],
    }

    for uid in all_user_ids:
        # Подписываем участника на чат
        await chat_manager.subscribe_to_chat(uid, chat.id)
        # Отправляем уведомление о новом чате (кроме создателя)
        if uid != user_id:
            await chat_manager.send_to_user(
                uid,
                {
                    "type": "chat_created",
                    "chat": chat_data,
                },
            )

    return {
        "data": {
            "id": chat.id,
            "name": chat.name,
            "chat_type": chat.chat_type,
            "is_internal": is_internal,
        }
    }


@router_private.post("/chats/{chat_id}/members")
async def add_member(req: Request, chat_id: int, body: AddMemberInput):
    """
    Добавить участника в чат.
    Требует права can_invite или is_admin.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство и право приглашать
    await ChatMember.check_can_invite(chat_id, user_id)

    try:
        chat = await env.models.chat.get(chat_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_ADD_TO_DIRECT_CHAT"})

    await chat.add_member(body.user_id)

    return {"success": True}


@router_private.patch("/chats/{chat_id}")
async def update_chat(req: Request, chat_id: int, body: ChatUpdate):
    """
    Обновить настройки чата (включая права по умолчанию).
    Изменение прав по умолчанию требует is_admin.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство
    member = await ChatMember.check_membership(chat_id, user_id)

    # Если меняются права по умолчанию - требуется админ
    changing_permissions = any(
        [
            body.default_can_read is not None,
            body.default_can_write is not None,
            body.default_can_invite is not None,
            body.default_can_pin is not None,
            body.default_can_delete_others is not None,
        ]
    )
    if changing_permissions and not member.is_admin:
        raise FaraException(
            {"content": "ADMIN_REQUIRED", "status_code": HTTP_403_FORBIDDEN}
        )

    try:
        chat = await env.models.chat.get(chat_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    # Нельзя редактировать direct чаты
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_EDIT_DIRECT_CHAT"})

    # Обновляем поля на объекте
    updated_fields = {}

    # Основные поля
    if body.name is not None:
        updated_fields["name"] = body.name
    if body.description is not None:
        updated_fields["description"] = body.description

    # Права по умолчанию
    if body.default_can_read is not None:
        updated_fields["default_can_read"] = body.default_can_read
    if body.default_can_write is not None:
        updated_fields["default_can_write"] = body.default_can_write
    if body.default_can_invite is not None:
        updated_fields["default_can_invite"] = body.default_can_invite
    if body.default_can_pin is not None:
        updated_fields["default_can_pin"] = body.default_can_pin
    if body.default_can_delete_others is not None:
        updated_fields["default_can_delete_others"] = (
            body.default_can_delete_others
        )

    if updated_fields:
        await chat.update(env.models.chat(**updated_fields))

    return {"success": True, "data": {"id": chat.id, **updated_fields}}


@router_private.patch("/chats/{chat_id}/members/{member_id}/permissions")
async def update_member_permissions(
    req: Request, chat_id: int, member_id: int
):
    """
    Обновить права участника чата.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    body = await req.json()

    # Проверяем что текущий пользователь админ
    await ChatMember.check_admin(chat_id, user_id)

    # Находим участника для обновления
    target_member = await ChatMember.get_membership(chat_id, member_id)
    if not target_member:
        raise FaraException(
            {"content": "MEMBER_NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    # Обновляем права
    perm_fields = {}
    for key in ("can_read", "can_write", "can_invite", "can_pin",
                "can_delete_others", "is_admin"):
        if key in body:
            perm_fields[key] = body[key]

    if perm_fields:
        await target_member.update(
            env.models.chat_member(**perm_fields)
        )

    return {"success": True}


@router_private.delete("/chats/{chat_id}/members/{member_id}")
async def remove_member(req: Request, chat_id: int, member_id: int):
    """
    Удалить участника из чата.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Для удаления других участников нужны права админа
    await ChatMember.check_admin(chat_id, user_id)

    try:
        chat = await env.models.chat.get(chat_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    # Нельзя удалять из direct чата
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_REMOVE_FROM_DIRECT_CHAT"})

    # Удаляем участника
    await chat.remove_member(member_id)

    return {"success": True}


@router_private.post("/chats/{chat_id}/leave")
async def leave_chat(req: Request, chat_id: int):
    """
    Покинуть чат.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство
    await ChatMember.check_membership(chat_id, user_id)

    try:
        chat = await env.models.chat.get(chat_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    # Нельзя покинуть direct чат
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_LEAVE_DIRECT_CHAT"})

    # Удаляем себя из участников
    await chat.remove_member(user_id)

    return {"success": True}


@router_private.delete("/chats/{chat_id}")
async def delete_chat(req: Request, chat_id: int):
    """
    Удалить чат (soft delete).
    Требует права админа.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Только админ может удалить чат
    await ChatMember.check_admin(chat_id, user_id)

    try:
        chat = await env.models.chat.get(chat_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    # Soft delete - устанавливаем active = false
    await chat.update(env.models.chat(active=False))

    return {"success": True}


@router_private.get("/chats/{chat_id}/connectors")
async def get_chat_connectors(req: Request, chat_id: int):
    """Получить список доступных коннекторов для чата."""
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство
    await ChatMember.check_membership(chat_id, user_id)

    try:
        chat = await env.models.chat.get(chat_id, fields=["id", "is_internal"])
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    connectors = await chat.get_available_connectors()
    return {"data": connectors}
