# Copyright 2025 FARA CRM
# Chat module - chats router

import asyncio
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
from ..models.chat_member import ChatMember

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session

router_private = APIRouter(
    tags=["Chat"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


def _resolve_direct_chat_name(
    chat_type: str,
    members: list[dict],
    current_user_id: int,
    stored_name: str,
) -> str:
    """Имя чата для отдачи клиенту.

    Для direct-чата:
      - имя всегда актуально, если собеседник сменил имя;
      - старые чаты «переименовываются» сами собой — имя не зависит от того,
        когда и под каким названием чат был создан;
      - имя корректно для каждого зрителя (A видит B, B видит A) — одного
        хранимого поля для этого в принципе не хватило бы.
    """
    if chat_type != "direct":
        return stored_name
    # Собеседник = любой участник, кроме текущего юзера. Партнёр (member_type
    # 'partner') никогда не является текущим юзером, поэтому исключаем только
    # user-участника с совпадающим id (member_type None трактуем как 'user').
    others = [
        m
        for m in members
        if not (
            m.get("member_type") in ("user", None)
            and m.get("id") == current_user_id
        )
    ]
    if not others:
        return stored_name  # чат с самим собой / собеседник не найден
    return others[0].get("name") or stored_name


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
    не являющиеся record-чатами:
      - chat_member.user_id = me AND chat_member.is_active = true
      - chat.active = true
      - chat.chat_type != 'record'

    Query-флаги снимают отдельные ограничения:
      - include_deleted=1  → снимает фильтр по chat.active (доступно всем)
      - include_record=1   → показывает record-чаты                 (доступно всем)
      - include_foreign=1  → снимает требование членства             (только админ,
                              для не-админа → 403 ADMIN_REQUIRED)

    Комбо-фильтрация:
    - is_internal=True + chat_type=direct → Внутренние личные
    - is_internal=True + chat_type=group  → Внутренние группы
    - is_internal=False + connector_type=telegram → Telegram чаты
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id
    is_sys_admin = bool(auth_session.user_id.is_admin)
    # Команды пользователя — уже в сессии (гидрируются при сборке), без запроса.
    my_team_ids = [t.id for t in (auth_session.user_id.team_ids or [])]

    # include_foreign разрешён только системному админу. Не-админам
    # бросаем 403, чтобы ошибка не маскировалась под «пустой результат».
    if bool(include_foreign) and not is_sys_admin:
        raise FaraException(
            {"content": "ADMIN_REQUIRED", "status_code": HTTP_403_FORBIDDEN}
        )

    session = env.apps.db.get_session()

    _show_foreign = bool(include_foreign) and is_sys_admin

    # Папку грузим РАНО: её kind влияет на базовый JOIN. Внешние папки
    # external_mine/external_all — глобальные, резолвятся по kind (не доменом,
    # как папки коннекторов): членство/team не выразить доменом над chat.
    # external_all = team-видимость (LEFT JOIN, членство необязательно).
    folder_row = None
    if folder_id is not None:
        _frows = await env.models.chat_folder.search(
            filter=[("id", "=", folder_id)],
            fields=["id", "domain", "connector_id", "kind"],
            limit=1,
        )
        if not _frows:
            return {"data": [], "total": 0}
        folder_row = _frows[0]
    folder_kind = folder_row.kind if folder_row else None

    # «Все» (внешние, team-scoped): из scope=all ИЛИ папки external_all.
    want_all = (scope == "all") or (folder_kind == "external_all")

    # Строим SQL динамически. Плейсхолдеры FROM/JOIN (join_params) держим
    # ОТДЕЛЬНО от WHERE (where_params): в итоговом тексте все JOIN-%s идут
    # раньше WHERE-%s, поэтому итоговый порядок = join_params + where_params.
    # Это убирает хрупкий insert(0) и делает scope/connector_type безопасными.
    join_params: list = []
    conditions: list[str] = []
    where_params: list = []

    if _show_foreign:
        base_query = """
            SELECT DISTINCT c.id, c.last_message_date
            FROM chat c
        """
    else:
        # LEFT JOIN + cm.user_id в ON: членство больше не обязательно, чтобы
        # scope=all мог показать team-scoped внешние чаты, где юзер НЕ участник.
        base_query = """
            SELECT DISTINCT c.id, c.last_message_date, cm.is_pinned
            FROM chat c
            LEFT JOIN chat_member cm
                ON c.id = cm.chat_id
               AND cm.is_active = true
               AND cm.user_id = %s
        """
        join_params.append(user_id)
        if want_all and my_team_ids:
            # Мои чаты (участник) ИЛИ чаты моих команд (team-scoped видимость).
            conditions.append(
                "(cm.user_id IS NOT NULL OR c.team_id = ANY(%s))"
            )
            where_params.append(my_team_ids)
        else:
            # 'mine' (дефолт) — только где я активный участник.
            conditions.append("cm.user_id IS NOT NULL")

    # Soft-delete: фильтр по active снимается флагом (доступно всем)
    if not bool(include_deleted):
        conditions.append("c.active = true")

    # Record-чаты: по умолчанию исключены. Флаг снимает исключение (доступно всем)
    if not bool(include_record):
        conditions.append("c.chat_type != 'record'")

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
            where_params.append(chat_type)

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
            # JOIN-плейсхолдер (текстово после cm-LEFT-JOIN) → в join_params.
            join_params.append(contact_type_id_for_filter.id)

    # Резолвинг папки (folder_row загружен рано). Три ветки:
    #   - external_mine/external_all → по kind: только внешние чаты
    #     (team-vs-membership уже задан базовым условием want_all выше);
    #   - папка коннектора → по chat_external_chat (не domain);
    #   - остальные → штатным ORM-поиском по domain (правила chat_folder уже
    #     ограничили выборку своими+глобальными папками).
    if folder_row is not None:
        if folder_kind in ("external_mine", "external_all"):
            conditions.append("c.is_internal = false")
        elif folder_row.connector_id:
            ext_rows = await session.execute(
                "SELECT DISTINCT chat_id FROM chat_external_chat "
                "WHERE connector_id = %s",
                (folder_row.connector_id.id,),
            )
            ext_ids = [r["chat_id"] for r in ext_rows]
            if not ext_ids:
                return {"data": [], "total": 0}
            conditions.append("c.id = ANY(%s)")
            where_params.append(ext_ids)
        else:
            domain = folder_row.domain or []
            if domain:
                matched = await env.models.chat.search(
                    filter=domain, fields=["id"], limit=10000
                )
                matched_ids = [m.id for m in matched]
                if not matched_ids:
                    return {"data": [], "total": 0}
                conditions.append("c.id = ANY(%s)")
                where_params.append(matched_ids)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    # Закреплённые чаты сверху. В foreign-режиме нет cm-джойна → без закрепа.
    # LEFT JOIN даёт cm.is_pinned=NULL у team-чатов, где юзер НЕ участник.
    # NULLS LAST кладёт их вниз (по умолчанию DESC = NULLS FIRST). Сортируем
    # именно по cm.is_pinned (а не COALESCE) — оно в списке SELECT DISTINCT,
    # иначе Postgres: "ORDER BY expressions must appear in select list".
    if _show_foreign:
        order_by = "c.last_message_date DESC NULLS LAST"
    else:
        order_by = (
            "cm.is_pinned DESC NULLS LAST, "
            "c.last_message_date DESC NULLS LAST"
        )

    chat_ids_query = f"""
        {base_query}
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
    """
    # Порядок: сначала все JOIN/FROM-плейсхолдеры, затем WHERE, затем LIMIT/OFFSET.
    all_params = join_params + where_params + [limit, offset]

    chat_id_rows = await session.execute(chat_ids_query, tuple(all_params))

    # Карта закрепа: id чата → is_pinned (в foreign-режиме поля нет → False).
    pinned_by_id = {
        row["id"]: bool(row.get("is_pinned", False)) for row in chat_id_rows
    }

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
            "create_datetime",
            "active",
        ],
        limit=limit,
    )

    # Получаем участников (пользователей и партнёров) через chat_member
    members_query = """
        SELECT cm.chat_id,
               COALESCE(u.id, p.id) as id,
               COALESCE(u.name, p.name) as name,
               CASE WHEN cm.user_id IS NOT NULL THEN 'user' ELSE 'partner' END as member_type,
               COALESCE(u.image, p.image) as image_id,
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
            id, chat_id, body, message_type, connector_type,
            author_user_id, author_partner_id, create_datetime
        FROM chat_message
        WHERE chat_id = ANY(%s) AND is_deleted = false
        ORDER BY chat_id, id DESC
    """
    last_messages_task = session.execute(last_messages_query, (chat_ids,))

    # Непрочитанные = сообщения в чате с id > watermark пользователя в этом чате.
    # Своих сообщений (author = текущий user) не считаем.
    # Watermark лежит в chat_member.last_read_message_id (NULL → 0).
    unread_query = """
        SELECT m.chat_id, COUNT(*) as unread_count
        FROM chat_message m
        JOIN chat_member cm
          ON cm.chat_id = m.chat_id
         AND cm.user_id = %s
         AND cm.is_active = true
        WHERE m.chat_id = ANY(%s)
          AND m.is_deleted = false
          AND (m.author_user_id IS NULL OR m.author_user_id != %s)
          AND m.id > COALESCE(cm.last_read_message_id, 0)
        GROUP BY m.chat_id
    """
    unread_task = session.execute(unread_query, (user_id, chat_ids, user_id))

    # ОТКЛЮЧЕНО: поле chat.connectors в ответе списка нигде на фронте не
    # читается (0 обращений к `.connectors` в frontend/src), а этот запрос
    # гонял JOIN по chat_member/contact/contact_type/chat_connector на КАЖДУЮ
    # загрузку сайдбара впустую. Живой пикер коннекторов — отдельный эндпоинт
    # GET /chats/{id}/connectors → Chat.get_available_connectors (там же и
    # phone-format фолбэк, ContactType.MATCH_SQL). Возвращаем connectors=[].
    # Если поле понадобится (мобилка/другой клиент) — раскомментировать блок,
    # connectors_task в gather, разбор connectors_raw и поле в result.
    # connectors_query = f"""
    #     SELECT DISTINCT ON (cm.chat_id, cc.id)
    #         cm.chat_id,
    #         cc.id as connector_id,
    #         cc.type as connector_type,
    #         cc.name as connector_name,
    #         c.id as contact_id,
    #         c.name as contact_value
    #     FROM chat_member cm
    #     JOIN contact c ON c.partner_id = cm.partner_id AND c.active = true
    #     JOIN contact_type ict ON ict.id = c.contact_type_id
    #     JOIN chat_connector cc ON cc.active = true
    #     JOIN contact_type cct ON cct.id = cc.contact_type_id
    #         AND {env.models.contact_type.MATCH_SQL}
    #     WHERE cm.chat_id = ANY(%s)
    #       AND cm.partner_id IS NOT NULL
    #       AND cm.is_active = true
    #     ORDER BY cm.chat_id, cc.id, (cct.id = ict.id) DESC
    # """
    # connectors_task = session.execute(connectors_query, (chat_ids,))

    # Выполняем параллельно (каждый запрос в своём соединении из пула)
    chats_orm, members_raw, last_messages_raw, unread_raw = (
        await asyncio.gather(
            chats_task,
            members_task,
            last_messages_task,
            unread_task,
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
                "member_type": m["member_type"],
                "image_id": m["image_id"],
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

    # ОТКЛЮЧЕНО вместе с connectors_query (см. выше) — поле не потребляется.
    # connectors_by_chat: dict[int, list] = {}
    # for conn in connectors_raw:
    #     cid = conn["chat_id"]
    #     if cid not in connectors_by_chat:
    #         connectors_by_chat[cid] = []
    #     connectors_by_chat[cid].append(
    #         {
    #             "id": conn["connector_id"],
    #             "type": conn["connector_type"],
    #             "name": conn["connector_name"],
    #             "contact_id": conn.get("contact_id"),
    #             "contact_value": conn.get("contact_value"),
    #         }
    #     )

    # Формируем результат
    result = []
    for chat in chats_sorted:
        chat_data = {
            "id": chat.id,
            "name": _resolve_direct_chat_name(
                chat.chat_type,
                members_by_chat.get(chat.id, []),
                user_id,
                chat.name,
            ),
            "chat_type": chat.chat_type,
            "is_internal": chat.is_internal,
            "active": chat.active,
            # Всегда []: connectors_query отключён (поле не читается фронтом).
            # Форму ответа сохраняем — тип Chat.connectors на фронте не опционален.
            "connectors": [],
            "last_message_date": (
                chat.last_message_date.isoformat()
                if chat.last_message_date
                else None
            ),
            "create_datetime": (
                chat.create_datetime.isoformat()
                if chat.create_datetime
                else None
            ),
            "unread_count": unread_by_chat.get(chat.id, 0),
            "members": members_by_chat.get(chat.id, []),
            "is_pinned": pinned_by_id.get(chat.id, False),
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
                "connector_type": last_msg.get("connector_type"),
                "author_id": author_user_id or author_partner_id,
                "author_name": author_name,
                "create_datetime": (
                    last_msg["create_datetime"].isoformat()
                    if last_msg["create_datetime"]
                    else None
                ),
            }
        else:
            chat_data["last_message"] = None

        result.append(chat_data)

    # Закреплённые сверху, затем по дате последнего сообщения.
    sorted_list = sorted(
        result,
        key=lambda x: (
            1 if x.get("is_pinned") else 0,
            x.get("last_message_date") or x.get("create_datetime") or "",
        ),
        reverse=True,
    )
    return {"data": sorted_list, "total": len(sorted_list)}


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

    # (1) unread + chat_type по каждому непрочитанному чату юзера. Формула та же,
    # что в get_chats: id > watermark, не свои, чат активен и не record, членство
    # активно. chat_type берём тут же — по нему резолвятся встроенные папки.
    unread_rows = await session.execute(
        """
        SELECT m.chat_id, c.chat_type, c.is_internal,
               COUNT(*) AS unread_count
        FROM chat_message m
        JOIN chat_member cm
          ON cm.chat_id = m.chat_id
         AND cm.user_id = %s
         AND cm.is_active = true
        JOIN chat c
          ON c.id = m.chat_id
         AND c.active = true
         AND c.chat_type != 'record'
        WHERE m.is_deleted = false
          AND (m.author_user_id IS NULL OR m.author_user_id != %s)
          AND m.id > COALESCE(cm.last_read_message_id, 0)
        GROUP BY m.chat_id, c.chat_type, c.is_internal
        """,
        (user_id, user_id),
    )
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
    total_all = sum(unread_by_chat.values())
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

    session = env.apps.db.get_session()

    # Проверка членства реализована через rule "@is_member" на модели chat:
    # chat.get(chat_id) бросит RecordNotFound для не-участников.
    chat = await env.models.chat.get(chat_id)

    # Получаем участников отдельным запросом

    members_query = """
        SELECT
            COALESCE(u.id, p.id) as id,
            COALESCE(u.name, p.name) as name,
            CASE WHEN cm.user_id IS NOT NULL THEN 'user' ELSE 'partner' END as member_type,
            COALESCE(u.image, p.image) as image_id,
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
            "member_type": m["member_type"],
            "image_id": m["image_id"],
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
            "name": _resolve_direct_chat_name(
                chat.chat_type,
                members,
                user_id,
                chat.name,
            ),
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
    Требует права can_invite или is_admin.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем членство и право приглашать
    await ChatMember.check_can_invite(chat_id, user_id)

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
    if changing_permissions or not member.is_admin:
        raise FaraException(
            {"content": "ADMIN_REQUIRED", "status_code": HTTP_403_FORBIDDEN}
        )

    chat = await env.models.chat.get(chat_id)

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
    req: Request,
    chat_id: int,
    member_id: int,
    payload: UpdateMemberPermissions,
):
    """
    Обновить права участника чата.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    # Проверяем что текущий пользователь админ
    await ChatMember.check_admin(chat_id, user_id)

    # Находим участника для обновления
    target_member = await ChatMember.get_membership(chat_id, member_id)
    if not target_member:
        raise FaraException(
            {"content": "MEMBER_NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

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

    # Для удаления других участников нужны права админа
    await ChatMember.check_admin(chat_id, user_id)

    chat = await env.models.chat.get(chat_id)

    # Нельзя удалять из direct чата
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_REMOVE_FROM_DIRECT_CHAT"})

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
    await ChatMember.check_membership(chat_id, user_id)

    chat = await env.models.chat.get(chat_id)

    # Нельзя покинуть direct чат
    if chat.chat_type == "direct":
        raise FaraException({"content": "CANNOT_LEAVE_DIRECT_CHAT"})

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
    - остальные: требует права админа чата (ChatMember.is_admin)
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
        # Группы/каналы — админ чата
        await ChatMember.check_admin(chat_id, user_id)

    # Soft delete
    await chat.update(env.models.chat(active=False))

    return {"success": True}


@router_private.post("/chats/{chat_id}/restore")
async def restore_chat(req: Request, chat_id: int):
    """
    Восстановить мягко удалённый чат (active=false → true).

    Права симметричны delete_chat:
    - direct: членство + системный is_admin (администратор системы);
    - остальные: права админа чата (ChatMember.is_admin).

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
        await ChatMember.check_admin(chat_id, user_id)

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
    member = await ChatMember.get_membership(chat_id, user_id)
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
    last = await env.models.chat_message.search(
        filter=[
            ("chat_id", "=", chat_id),
            ("connector_type", "=", "email"),
            ("is_deleted", "=", False),
        ],
        fields=["id", "body"],
        sort="id",
        order="DESC",
        limit=1,
    )

    subject = None
    if last and last[0].body:
        try:
            data = json.loads(last[0].body)
            if isinstance(data, dict):
                subject = data.get("subject")
        except (ValueError, TypeError):
            subject = None

    return {"data": {"subject": subject or chat.name or ""}}
