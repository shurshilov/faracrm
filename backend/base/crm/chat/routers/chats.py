# Copyright 2025 FARA CRM
# Chat module - chats router

import json
import logging
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request, Query
from starlette.status import HTTP_404_NOT_FOUND, HTTP_403_FORBIDDEN

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException
from ..schemas.chat import (
    ChatCreate,
    ChatUpdate,
    AddMemberInput,
    UpdateMemberPermissions,
    ChatPin,
)
from ..models.chat_member import ChatMember, ChatPermissions

log = logging.getLogger(__name__)

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
    search: str | None = Query(
        None,
        max_length=200,
        description="Поиск: имя чата или участника (пользователь/партнёр), "
        "без учёта регистра, среди всех доступных чатов",
    ),
    is_internal: bool | None = Query(
        None, description="Фильтр: True=внутренние, False=внешние, None=все"
    ),
    chat_type: str | None = Query(
        None, description="Фильтр по типу: direct, group"
    ),
    connector_type: str | None = Query(
        None, description="Фильтр по коннектору: telegram, whatsapp, etc"
    ),
    folder_id: int | None = Query(
        None,
        description="Фильтр по папке чатов пользователя (chat_folder.id)",
    ),
    include_deleted: int = Query(
        0, description="Показать удалённые чаты (active=false)"
    ),
    include_record: int = Query(
        0, description="Показать record-чаты (chat_type='record')"
    ),
    include_foreign: int = Query(
        0,
        description="Admin-only: показать чужие чаты "
        "(где текущий user не активный мембер)",
    ),
    scope: str | None = Query(
        None,
        description="Внешние чаты: 'mine'=где я участник (дефолт), "
        "'all'=мои команды + членство (team-scoped видимость)",
    ),
):
    """
    Получить список чатов текущего пользователя.

    По умолчанию пользователь (в т.ч. админ) видит только свои активные чаты,
    не являющиеся record-чатами. Query-флаги снимают отдельные ограничения:
      - include_deleted=1  → снимает фильтр по chat.active (доступно всем)
      - include_record=1   → показывает record-чаты (доступно всем)
      - include_foreign=1  → снимает требование членства (только админ,
                              для не-админа → 403 ADMIN_REQUIRED)

    Как собирается список — Chat.list_for_user.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session

    # include_foreign разрешён только системному админу. Не-админам
    # бросаем 403, чтобы ошибка не маскировалась под «пустой результат».
    if include_foreign and not auth_session.user_id.is_admin:
        raise FaraException(
            {"content": "ADMIN_REQUIRED", "status_code": HTTP_403_FORBIDDEN}
        )

    chats = await env.models.chat.list_for_user(
        auth_session.user_id,
        limit=limit,
        offset=offset,
        search=search,
        is_internal=is_internal,
        chat_type=chat_type,
        connector_type=connector_type,
        folder_id=folder_id,
        include_deleted=bool(include_deleted),
        include_record=bool(include_record),
        include_foreign=bool(include_foreign),
        scope=scope,
    )
    return {"data": chats, "total": len(chats)}


@router_private.get("/chats/folders/unread")
async def get_folders_unread(req: Request):
    """Кол-во непрочитанных сообщений по каждой папке для текущего юзера.

    Считаем НА ЛЕТУ (ничего не храним) — тем же способом, что и бейджик
    вверху справа: сначала один запрос даёт unread по каждому чату юзера,
    затем для каждой папки суммируем unread по её чатам. Членство чата в
    папке резолвится ровно как в get_chats (папка коннектора → через
    chat_external_chat; обычная → domain над chat), поэтому счётчик всегда
    совпадает с тем, что реально видно при открытии папки.

    Хранить нельзя: один чат входит сразу в несколько папок («Все» +
    «Личные» + папка коннектора), unread — per-user (watermark в
    chat_member), а папки глобальные; domain папки может меняться.

    Ответ: {"data": {"<folder_id>": <count>, ...}} — только папки с count>0
    (фронт рисует бейдж лишь при >0).

    Без N+1: набор непрочитанных чатов у юзера мал, поэтому вместо «на каждую
    папку — свой запрос за её чатами» делаем фиксированные 3 запроса и решаем
    принадлежность в памяти:
      (1) unread + chat_type по каждому непрочитанному чату;
      (2) карта чат→коннектор(ы) для этих чатов (bulk, один IN-запрос);
      (3) список папок (как их берёт сайдбар — limit/сортировка те же).
    Встроенные папки резолвим по kind/chat_type, папки коннектора — по карте
    из (2). Произвольный domain кастомной папки (редко) — единственный случай,
    где нужен запрос, и тот сужен до непрочитанных (id IN ...).
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    session = env.apps.db.get_session()

    # (1) unread + chat_type по каждому непрочитанному чату юзера. Формула та
    # же, что в списке чатов (ChatMessage.unread_counts). chat_type берём тут
    # же — по нему резолвятся встроенные папки.
    unread_rows = await env.models.chat_message.unread_counts(user_id)
    if not unread_rows:
        return {"data": {}}

    unread_by_chat: dict[int, int] = {
        r["chat_id"]: r["unread_count"] for r in unread_rows
    }
    type_by_chat: dict[int, str] = {
        r["chat_id"]: r["chat_type"] for r in unread_rows
    }
    # is_internal нужен, чтобы внутренние папки (all/direct/group) не считали
    # внешние чаты. Этот цикл резолвит папки по kind, а НЕ по domain, поэтому
    # фильтр из DEFAULT_GLOBAL_FOLDERS.domain сюда не долетает — дублируем его.
    internal_by_chat: dict[int, bool] = {
        r["chat_id"]: r["is_internal"] for r in unread_rows
    }
    unread_ids = list(unread_by_chat)
    total_internal = sum(
        cnt for ch, cnt in unread_by_chat.items() if internal_by_chat.get(ch)
    )
    # Внешние = не-внутренние. external_all и external_mine дают одну сумму:
    # непрочитанное считается по watermark участника (запрос выше джойнит
    # chat_member по user_id), а он есть только там, где юзер УЖЕ участник —
    # то есть в «Мои». Team-видимые, но не свои чаты watermark'а не имеют и в
    # unread не попадают, поэтому «Все» и «Мои» по непрочитанным совпадают.
    total_external = sum(
        cnt
        for ch, cnt in unread_by_chat.items()
        if not internal_by_chat.get(ch)
    )

    # (2) Карта непрочитанный чат → id коннектора(ов) — один bulk-запрос,
    # вместо запроса на каждую папку коннектора.
    conn_rows = await session.execute(
        "SELECT chat_id, connector_id FROM chat_external_chat "
        "WHERE chat_id = ANY(%s)",
        (unread_ids,),
    )
    connectors_by_chat: dict[int, set[int]] = {}
    for r in conn_rows:
        connectors_by_chat.setdefault(r["chat_id"], set()).add(
            r["connector_id"]
        )

    # (3) Папки — как их запрашивает сайдбар (ChatSidebar): limit 100,
    # сортировка по sequence. Правила chat_folder отдают свои + глобальные.
    folders = await env.models.chat_folder.search(
        filter=[],
        fields=["id", "domain", "connector_id", "kind"],
        limit=100,
        sort="sequence",
        order="ASC",
    )

    result: dict[str, int] = {}
    for folder in folders:
        conn = folder.connector_id
        if conn:
            # Папка коннектора → чаты с этим connector_id (из карты п.2).
            cid = conn.id
            total = sum(
                cnt
                for ch, cnt in unread_by_chat.items()
                if cid in connectors_by_chat.get(ch, ())
            )
        elif folder.kind == "direct":
            # Внутренняя папка → только внутренние чаты (см. internal_by_chat).
            total = sum(
                cnt
                for ch, cnt in unread_by_chat.items()
                if type_by_chat[ch] == "direct" and internal_by_chat.get(ch)
            )
        elif folder.kind == "group":
            total = sum(
                cnt
                for ch, cnt in unread_by_chat.items()
                if type_by_chat[ch] in ("group", "channel")
                and internal_by_chat.get(ch)
            )
        elif folder.kind in ("external_all", "external_mine"):
            # Внешние папки → только внешние чаты. Ветка ДО catch-all ниже: у
            # них domain=None, иначе они провалились бы в total_internal и
            # показывали 0.
            total = total_external
        elif folder.kind == "all" or not folder.domain:
            # «Все» под «Внутренними» = все ВНУТРЕННИЕ непрочитанные (внешние
            # живут в своей секции и своих папках external_*).
            total = total_internal
        else:
            # Кастомная папка с произвольным domain. Резолвим по domain, но
            # узко — только по непрочитанным (id IN unread_ids), не по всем
            # чатам. (domain) AND (id in U): domain оборачиваем в подсписок,
            # иначе OR внутри него «утечёт» за пределы условия по id.
            matched = await env.models.chat.search(
                filter=[folder.domain, ["id", "in", unread_ids]],
                fields=["id"],
            )
            total = sum(unread_by_chat[m.id] for m in matched)

        if total:
            result[str(folder.id)] = total

    return {"data": result}


@router_private.post("/chats/{chat_id}/pin")
async def pin_chat(req: Request, chat_id: int, body: ChatPin):
    """
    Закрепить/открепить чат для текущего пользователя.

    Закреп — per-user состояние (chat_member.is_pinned). Закреплённые чаты
    идут сверху списка getChats.
    """
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем активное членство (бросит ACCESS_DENIED если не участник).
    member = await ChatMember.check_membership(chat_id, user_id)

    env: "Environment" = req.app.state.env
    await member.update(env.models.chat_member(is_pinned=body.pinned))

    return {"success": True, "is_pinned": body.pinned}


@router_private.get("/chats/{chat_id}")
async def get_chat(req: Request, chat_id: int):
    """
    Получить информацию о чате.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверка членства реализована через rule "@is_member" на модели chat:
    # chat.get(chat_id) бросит RecordNotFound для не-участников.
    chat = await env.models.chat.get(chat_id)
    members = (await ChatMember.list_for_chats([chat_id])).get(chat_id, [])

    return {
        "data": {
            "id": chat.id,
            "name": chat.display_name(members, user_id),
            "chat_type": chat.chat_type,
            "description": chat.description,
            "is_internal": chat.is_internal,
            "is_public": chat.is_public,
            "create_datetime": (
                chat.create_datetime.isoformat()
                if chat.create_datetime
                else None
            ),
            "members": members,
            # Default permissions
            "default_can_read": chat.default_can_read,
            "default_can_write": chat.default_can_write,
            "default_can_invite": chat.default_can_invite,
            "default_can_remove": chat.default_can_remove,
            "default_can_pin": chat.default_can_pin,
            "default_can_delete_others": chat.default_can_delete_others,
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

    # ── Инварианты модели 1:1 с партнёром (императивно, ДО создания) ──────
    # Рулом это не выразить: (1) «есть партнёр» — не поле chat, а is_internal
    # вычисляется триггером ПОСЛЕ добавления мемберов (create-правило же
    # перепроверяет запись сразу после INSERT); (2) уникальность — кросс-
    # записевая. Поэтому проверяем здесь, по известным partner_ids.
    #
    # (1) ЛИЧНЫЙ (direct) чат С ПАРТНЁРОМ запрещён: переписка с клиентом идёт в
    #     ЕДИНЫЙ ГРУППОВОЙ чат партнёра. Личный — только между пользователями.
    if body.chat_type == "direct" and has_partners:
        raise FaraException(
            {
                "content": "DIRECT_PARTNER_CHAT_FORBIDDEN",
                "detail": "Личный чат с партнёром запрещён — используйте "
                "общий чат партнёра",
            }
        )
    # (2) У партнёра может быть только ОДИН внешний чат: если у любого из
    #     указанных партнёров уже есть внешний чат (group ИЛИ direct), где он
    #     активный участник — второй создавать нельзя.
    if has_partners:
        # Один запрос по всем партнёрам сразу (ANY) — без N+1.
        _taken_rows = await env.apps.db.get_session().execute(
            "SELECT DISTINCT cm.partner_id FROM chat c "
            "JOIN chat_member cm ON cm.chat_id = c.id "
            "  AND cm.partner_id = ANY(%s) AND cm.is_active = true "
            "WHERE c.is_internal = false AND c.active = true "
            "  AND c.chat_type != 'record'",
            (body.partner_ids,),
        )
        _taken = [r["partner_id"] for r in _taken_rows]
        if _taken:
            raise FaraException(
                {
                    "content": "PARTNER_CHAT_EXISTS",
                    "detail": f"У партнёров {sorted(_taken)} уже есть "
                    "внешний чат — второй создавать нельзя",
                }
            )

    async with env.apps.db.get_transaction():
        if body.chat_type == "direct":
            # direct+partner уже отсечён выше → только внутренний user-user
            # (ровно один собеседник-пользователь).
            if len(body.user_ids) != 1:
                raise FaraException(
                    {"content": "DIRECT_CHAT_REQUIRES_ONE_RECIPIENT"}
                )
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

    # Уведомляем участников через шину, а не локальным фан-аутом: они сидят
    # на разных воркерах (см. секцию PRESENCE в websocket/manager.py), и
    # участник с чужого воркера раньше не получал chat_created вовсе.
    # Данные чата клиент дочитает рефетчем списка, как и раньше.
    await env.apps.chat.chat_manager.notify_new_chat_bulk(
        all_user_ids, chat.id
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
    Требует права can_invite; без него — админ чата или администратор
    системы.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Системный админ, админ чата или участник с правом can_invite
    member = await ChatMember.get_membership(chat_id, user_id)
    ChatMember.check_permissions(member, ChatPermissions(can_invite=True))

    chat = await env.models.chat.get(chat_id)

    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_ADD_TO_DIRECT_CHAT"})

    await chat.add_member(body.user_id)

    # Системное сообщение «actor добавил(а) target»
    try:
        actor = await env.models.user.get(user_id, fields=["id", "name"])
        target = await env.models.user.get(body.user_id, fields=["id", "name"])
        await env.models.chat_message.post_system_message(
            chat_id=chat_id,
            event="member_added",
            params={
                "actor_id": actor.id,
                "actor_name": actor.name,
                "target_id": target.id,
                "target_name": target.name,
            },
        )
    except Exception as exc:
        log.warning("add_member system message skipped: %s", exc)

    return {"success": True}


@router_private.patch("/chats/{chat_id}")
async def update_chat(req: Request, chat_id: int, body: ChatUpdate):
    """
    Обновить настройки чата (включая права по умолчанию).
    Требует админа чата или администратора системы.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    member = await ChatMember.get_membership(chat_id, user_id)
    ChatMember.check_permissions(member)

    chat = await env.models.chat.get(chat_id)

    # Нельзя редактировать direct чаты
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_EDIT_DIRECT_CHAT"})

    # Обновляем только переданные поля
    updated_fields = body.model_dump(exclude_none=True)
    if updated_fields:
        await chat.update(env.models.chat(**updated_fields))

    return {"success": True, "data": {"id": chat.id, **updated_fields}}


@router_private.patch("/chats/{chat_id}/members/{member_id}/permissions")
async def update_member_permissions(
    req: Request,
    chat_id: int,
    member_id: int,
    payload: UpdateMemberPermissions,
):
    """
    Обновить права участника чата.
    Требует админа чата или администратора системы.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    member = await ChatMember.get_membership(chat_id, user_id)
    ChatMember.check_permissions(member)

    # Находим участника для обновления
    target_member = await ChatMember.get_membership(chat_id, member_id)
    if not target_member:
        raise FaraException(
            {"content": "MEMBER_NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    if payload.is_admin is False:
        await target_member.check_not_last_admin(chat_id)

    # Обновляем только переданные поля
    perm_fields = payload.model_dump(exclude_none=True)
    if perm_fields:
        await target_member.update(env.models.chat_member(**perm_fields))

    return {"success": True}


@router_private.delete("/chats/{chat_id}/members/{member_id}")
async def remove_member(req: Request, chat_id: int, member_id: int):
    """
    Удалить участника из чата.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Системный админ, админ чата или участник с правом can_remove
    member = await ChatMember.get_membership(chat_id, user_id)
    ChatMember.check_permissions(member, ChatPermissions(can_remove=True))

    chat = await env.models.chat.get(chat_id)

    # Нельзя удалять из direct чата
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_REMOVE_FROM_DIRECT_CHAT"})

    target_member = await ChatMember.get_membership(chat_id, member_id)
    if target_member:
        await target_member.check_not_last_admin(chat_id)

    # Удаляем участника (мягко: is_active=False, запись user не трогается)
    await chat.remove_member(member_id)

    # Системное сообщение «actor удалил(а) target»
    try:
        actor = await env.models.user.get(user_id, fields=["id", "name"])
        target = await env.models.user.get(member_id, fields=["id", "name"])
        await env.models.chat_message.post_system_message(
            chat_id=chat_id,
            event="member_removed",
            params={
                "actor_id": actor.id,
                "actor_name": actor.name,
                "target_id": target.id,
                "target_name": target.name,
            },
        )
    except Exception as exc:
        log.warning("remove_member system message skipped: %s", exc)

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
    member = await ChatMember.check_membership(chat_id, user_id)

    chat = await env.models.chat.get(chat_id)

    # Нельзя покинуть direct чат
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_LEAVE_DIRECT_CHAT"})

    await member.check_not_last_admin(chat_id)

    # Удаляем себя из участников (мягко: is_active=False)
    await chat.remove_member(user_id)

    # Системное сообщение «actor покинул(а) чат»
    try:
        actor = await env.models.user.get(user_id, fields=["id", "name"])
        await env.models.chat_message.post_system_message(
            chat_id=chat_id,
            event="member_left",
            params={
                "actor_id": actor.id,
                "actor_name": actor.name,
            },
        )
    except Exception as exc:
        log.warning("leave_chat system message skipped: %s", exc)

    return {"success": True}


@router_private.delete("/chats/{chat_id}")
async def delete_chat(req: Request, chat_id: int):
    """
    Удалить чат (soft delete).
    - direct чат: может удалить пользователь с is_admin (администратор системы)
    - остальные: админ чата (ChatMember.is_admin) или администратор системы
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    chat = await env.models.chat.get(chat_id, fields=["id", "chat_type"])

    if chat.chat_type == "direct":
        # Direct чат — проверяем членство + системный is_admin
        await ChatMember.check_membership(chat_id, user_id)
        if not auth_session.user_id.is_admin:
            raise FaraException(
                {
                    "content": "ADMIN_REQUIRED",
                    "status_code": HTTP_403_FORBIDDEN,
                }
            )
    else:
        # Группы/каналы — админ чата или администратор системы
        member = await ChatMember.get_membership(chat_id, user_id)
        ChatMember.check_permissions(member)

    # Soft delete
    await chat.update(env.models.chat(active=False))

    return {"success": True}


@router_private.post("/chats/{chat_id}/restore")
async def restore_chat(req: Request, chat_id: int):
    """
    Восстановить мягко удалённый чат (active=false → true).

    Права симметричны delete_chat:
    - direct: членство + системный is_admin (администратор системы);
    - остальные: админ чата (ChatMember.is_admin) или администратор системы.

    Правила модели chat пропускают участника к записи независимо от active,
    поэтому удалённый чат находится штатным get. Само восстановление и
    live-переоткрытие в сайдбаре делает chat.reactivate()
    (идемпотентно, если чат уже активен).
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    chat = await env.models.chat.get(
        chat_id, fields=["id", "chat_type", "active"]
    )

    if chat.chat_type == "direct":
        await ChatMember.check_membership(chat_id, user_id)
        if not auth_session.user_id.is_admin:
            raise FaraException(
                {
                    "content": "ADMIN_REQUIRED",
                    "status_code": HTTP_403_FORBIDDEN,
                }
            )
    else:
        member = await ChatMember.get_membership(chat_id, user_id)
        ChatMember.check_permissions(member)

    await chat.reactivate()

    return {"success": True}


@router_private.get("/chats/{chat_id}/connectors")
async def get_chat_connectors(req: Request, chat_id: int):
    """Получить список доступных коннекторов для чата."""
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверка членства реализована через rule "@is_member":
    # chat.get(chat_id) бросит RecordNotFound для не-участников.
    chat = await env.models.chat.get(chat_id, fields=["id", "is_internal"])

    connectors = await chat.get_available_connectors(current_user_id=user_id)

    # Коннектор по умолчанию текущего юзера в этом чате (галочка в свитчере).
    # null = internal — подставляется при открытии чата на фронте.
    member = await ChatMember.get_membership(
        chat_id, user_id, fields=["id", "default_connector_id"]
    )
    default_connector_id = (
        member.default_connector_id.id
        if member and member.default_connector_id
        else None
    )
    return {"data": connectors, "default_connector_id": default_connector_id}


@router_private.post("/chats/{chat_id}/default-connector")
async def set_chat_default_connector(req: Request, chat_id: int):
    """
    Сохранить коннектор по умолчанию для ТЕКУЩЕГО юзера в этом чате.

    Тело: {"connector_id": <id> | null}. null = internal. Пишется в
    chat_member.default_connector_id (per-user, как закрепление чата).
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    payload = await req.json()
    connector_id = (payload or {}).get("connector_id")

    member = await ChatMember.get_membership(chat_id, user_id)
    if not member:
        return {"data": {"ok": False, "error": "not a member"}}

    await member.update(
        env.models.chat_member(
            default_connector_id=(
                env.models.chat_connector(id=connector_id)
                if connector_id
                else None
            )
        ),
        fields=["default_connector_id"],
    )
    return {"data": {"ok": True, "connector_id": connector_id}}


@router_private.get("/chats/{chat_id}/email-subject")
async def get_chat_email_subject(req: Request, chat_id: int):
    """
    Тема письма по умолчанию для виджета email.

    Правило: если в чате уже есть сообщение с темой (последнее письмо) —
    берём его тему (продолжение переписки). Иначе — имя чата. Пользователь
    в виджете может переопределить.
    """
    env: "Environment" = req.app.state.env

    # Проверка членства — через rule "@is_member" (RecordNotFound не-участнику).
    chat = await env.models.chat.get(chat_id, fields=["id", "name"])

    # Тема хранится внутри body последнего письма (email-формат
    # {subject, html}), поэтому берём body последнего email-сообщения и
    # парсим тему. Если писем нет — имя чата.
    last = await env.models.chat_message.search_one(
        filter=[
            ("chat_id", "=", chat_id),
            ("connector_type", "=", "email"),
            ("is_deleted", "=", False),
        ],
        fields=["id", "body"],
        sort="id",
        order="DESC",
    )

    subject = None
    if last and last.body:
        try:
            data = json.loads(last.body)
            if isinstance(data, dict):
                subject = data.get("subject")
        except (ValueError, TypeError):
            subject = None

    return {"data": {"subject": subject or chat.name or ""}}
