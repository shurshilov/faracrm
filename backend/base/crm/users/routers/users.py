from datetime import datetime, timedelta, timezone
import secrets
from typing import TYPE_CHECKING, Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.security.exceptions import AuthException
from backend.base.crm.users.models.users import User
from backend.base.crm.users.schemas.users import (
    UserSigninInput,
    ChangePasswordInput,
    CopyUserInput,
    CopyUserOutput,
)
from backend.base.crm.security.models.sessions import Session
from backend.base.system.schemas.base_schema import Id, Password

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

router_public = APIRouter(
    tags=["User"],
)

router_private = APIRouter(
    tags=["User"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


@router_private.post("/users/copy", response_model=CopyUserOutput)
async def copy_user(req: Request, payload: CopyUserInput):
    """Копирование пользователя с выбранными данными."""
    env: "Environment" = req.app.state.env

    # Получаем исходного пользователя со всеми нужными полями
    async with env.apps.db.get_transaction():
        source_user = await env.models.user.search(
            filter=[("id", "=", payload.source_user_id)],
            fields=[
                "id",
                "name",
                "login",
                "password_hash",
                "password_salt",
                "is_admin",
                "image",
                "role_ids",
                "lang_ids",
                "contact_ids",
            ],
        )
        source_user = source_user[0]

        if not source_user:
            return JSONResponse(
                content={"error": "User not found"}, status_code=404
            )

        # Проверяем уникальность логина
        existing = await env.models.user.search(
            filter=[("login", "=", payload.login)],
            limit=1,
            fields=["id"],
        )
        if existing:
            return JSONResponse(
                content={"error": "User with this login already exists"},
                status_code=400,
            )

        # Формируем данные нового пользователя
        new_user = User()
        new_user.name = payload.name
        new_user.login = payload.login

        # Копируем пароль если нужно
        if payload.copy_password:
            new_user.password_hash = source_user.password_hash
            new_user.password_salt = source_user.password_salt

        # Копируем флаг суперпользователя
        if payload.copy_is_admin:
            new_user.is_admin = source_user.is_admin

        # Создаём пользователя
        id = await env.models.user.create(payload=new_user)
        new_user.id = id

        # Копируем роли
        if payload.copy_roles and source_user.role_ids:
            role_ids = [r.id for r in source_user.role_ids]
            if role_ids:
                # Используем Many2many связь
                await new_user.update_with_relations(
                    User(id=id, role_ids={"selected": role_ids}),
                )

        # Копируем языки
        # if payload.copy_languages and source_user.lang_ids:
        #     lang_ids = [l.id for l in source_user.lang_ids]
        #     if lang_ids:
        #         await new_user.update_with_relations(
        #             payload=User(
        #                 id=id, lang_ids={"selected": lang_ids}
        #             ),
        #             fields=["lang_ids"],
        #         )

        # Копируем файлы (создаём копии записей attachments)
        # if payload.copy_files and source_user.image_ids:
        #     for attachment in source_user.image_ids:
        #         new_attachment = env.models.attachment(
        #             name=attachment.name,
        #             res_model="user",
        #             res_id=new_user.id,
        #             mimetype=attachment.mimetype,
        #             storage_id=attachment.storage_id,
        #             storage_file_url=attachment.storage_file_url,
        #         )
        #         await env.models.attachment.create(payload=new_attachment)

        # Копируем контакты
        if payload.copy_contacts and source_user.contact_ids:
            new_contacts = [
                env.models.contact(
                    name=contact.name,
                    contact_type=contact.contact_type,
                    user_id=new_user,
                    is_primary=contact.is_primary,
                )
                for contact in source_user.contact_ids
            ]
            if new_contacts:
                await env.models.contact.create_bulk(new_contacts)

        return CopyUserOutput(
            id=new_user.id,
            name=new_user.name,
            login=new_user.login,
        )


@router_private.post("/users/password_change")
async def password_change(req: Request, payload: ChangePasswordInput):
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session

    if payload.user_id is None:
        payload.user_id = req.state.session.user_id.id

    user = await env.models.user.get(id=payload.user_id)
    if user:
        await user.password_change(env, payload.password, auth_session)
        return {"success": True}
    else:
        return JSONResponse(content={"error": "#NOT_FOUND"}, status_code=404)


@router_public.post("/signin")
async def signin(req: Request, payload: UserSigninInput):
    env: "Environment" = req.app.state.env

    async with env.apps.db.get_transaction():
        # проверить существует ли пользователь по введеному логину
        user_id = await env.models.user.search(
            filter=[("login", "=", payload.login)],
            limit=1,
            fields=["id", "name", "password_hash", "password_salt"],
        )
        if not user_id:
            raise AuthException.UserNotExist

        user_id = user_id[0]
        # сделать хеш из введеного пароля, с использованием старой соли
        password_hash = user_id.generate_password_hash_salt_old(
            password=payload.password
        )

        # сравнить с базой
        if password_hash != user_id.password_hash:
            raise AuthException.PasswordFailed

        # генерация токена
        token = secrets.token_urlsafe(nbytes=64)

        # создать сессию
        now = datetime.now(timezone.utc)
        ttl = await Session.get_ttl()
        # оставить только поля id, name
        # чтобы не хранить хеш и соль в сессии на фронте для безопасности
        clear_user_id = User(**user_id.json(include={"id", "name"}))
        session = Session(
            user_id=clear_user_id,
            token=token,
            ttl=ttl,
            expired_datetime=now + timedelta(seconds=ttl),
            create_user_id=clear_user_id,
            update_user_id=clear_user_id,
        )
        await env.models.session.create(payload=session)

        # вернуть токен, для сохранения в локал сторейдж
        # и последующего использования на фронтенде
        return session
