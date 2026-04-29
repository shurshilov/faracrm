# Copyright 2025 FARA CRM
# Attachments Yandex Disk module - OAuth2 callback router

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx

from backend.base.crm.auth_token.app import AuthTokenApp

from fastapi import Depends, APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

# URL'ы Яндекс OAuth2
YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
# YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/verification_code"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"

# При регистрации приложения на oauth.yandex.ru нужно выбрать права:
# - cloud_api:disk.read    (Чтение Яндекс.Диска)
# - cloud_api:disk.write   (Запись Яндекс.Диска)
# - cloud_api:disk.app_folder (опционально - доступ только к папке приложения)
# Сами scopes в /authorize Яндекс не принимает — они зашиты в приложение,
# но мы их перечисляем в комментарии для документации.

router_public = APIRouter(
    tags=["Attachments Yandex OAuth"],
    prefix="/yandex",
    dependencies=[Depends(AuthTokenApp.use_system_session)],
)


def _normalize_api_url(api_url: str) -> str:
    """
    Привести URL CRM к виду, пригодному для redirect_uri.
    Локальный 127.0.0.1 -> localhost; http -> https для не-localhost.
    """
    if api_url.startswith(r"http://127.0.0.1"):
        api_url = "http://localhost" + api_url[16:]
    elif api_url.startswith("http:") and "localhost" not in api_url:
        api_url = "https:" + api_url[5:]
    return api_url.rstrip("/")


@router_public.get("/callback")
async def oauth2_callback(req: Request):
    """
    OAuth2 callback endpoint для Яндекс.Диска.

    Яндекс перенаправляет сюда после авторизации пользователя.
    Получает authorization code и обменивает на access/refresh токены.

    Query parameters:
    - code: Authorization code от Яндекса
    - state: Verification code для поиска storage записи
    - error: Ошибка авторизации (если есть)
    """
    # Проверяем наличие параметра state
    state = req.query_params.get("state")
    if not state:
        logger.warning("Yandex OAuth callback called without state parameter")
        return RedirectResponse(url="/")

    # Проверяем ошибку авторизации
    error = req.query_params.get("error")
    if error:
        error_description = req.query_params.get(
            "error_description", "Unknown error"
        )
        logger.error("Yandex OAuth error: %s - %s", error, error_description)
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Authorization Error</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {error}</p>
                <p>Description: {error_description}</p>
                <p><a href="/">Return to main page</a></p>
            </body>
            </html>
            """,
            status_code=400,
        )

    code = req.query_params.get("code")
    if not code:
        logger.warning("Yandex OAuth callback called without code")
        return HTMLResponse(
            content="""
            <html>
            <head><title>Error</title></head>
            <body>
                <h1>Authorization Error</h1>
                <p>Missing authorization code.</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    env: "Environment" = req.app.state.env

    # Ищем storage по verify_code
    storage_list = await env.models.attachment_storage.search(
        filter=[
            ("type", "=", "yandex"),
            ("yandex_verify_code", "=", state),
        ],
        limit=1,
        fields=[
            "id",
            "name",
            "yandex_client_id",
            "yandex_client_secret",
            "yandex_verify_code",
        ],
    )

    if not storage_list:
        logger.warning("Yandex storage not found for state: %s", state)
        return HTMLResponse(
            content="""
            <html>
            <head><title>Error</title></head>
            <body>
                <h1>Storage Not Found</h1>
                <p>The storage configuration was not found. Please try again.</p>
                <p><a href="/">Return to main page</a></p>
            </body>
            </html>
            """,
            status_code=404,
        )

    storage = storage_list[0]

    if not (storage.yandex_client_id and storage.yandex_client_secret):
        logger.error("Missing client credentials for storage %s", storage.id)
        return HTMLResponse(
            content="""
            <html>
            <head><title>Error</title></head>
            <body>
                <h1>Configuration Error</h1>
                <p>Client ID or Client Secret is missing.</p>
                <p><a href="/">Return to main page</a></p>
            </body>
            </html>
            """,
            status_code=400,
        )

    try:
        api_url = await env.models.system_settings.get_api_url()
        api_url = _normalize_api_url(api_url)
        redirect_uri = f"{api_url}/yandex/callback"

        # Обмениваем code на токены
        async with httpx.AsyncClient(timeout=60.0) as client:
            token_resp = await client.post(
                YANDEX_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": storage.yandex_client_id,
                    "client_secret": storage.yandex_client_secret,
                    "redirect_uri": redirect_uri,
                },
            )

        if token_resp.status_code != 200:
            logger.error(
                "Yandex token exchange failed: %s %s",
                token_resp.status_code,
                token_resp.text,
            )
            raise ValueError(
                f"Token exchange failed: {token_resp.status_code}"
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 0) or 0)

        if not access_token:
            raise ValueError("No access_token in Yandex response")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Сохраняем credentials в storage
        storage_new = env.models.attachment_storage(
            yandex_access_token=access_token,
            yandex_refresh_token=refresh_token,
            yandex_token_expires_at=expires_at.isoformat(),
            yandex_auth_state="authorized",
            yandex_verify_code=None,  # Очищаем использованный код
        )
        await storage.update(payload=storage_new)

        logger.info(
            "Yandex Disk authorized successfully for storage %s", storage.id
        )

        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>Authorization Successful</title>
                <script>
                    if (window.opener) {{
                        window.opener.location.reload();
                        window.close();
                    }} else {{
                        window.location.href = '/attachments_storage/{storage.id}';
                    }}
                </script>
            </head>
            <body>
                <h1>Authorization Successful!</h1>
                <p>Yandex Disk has been connected successfully.</p>
                <p>You can close this window or
                   <a href="/attachments_storage/{storage.id}">return to storage settings</a>.</p>
            </body>
            </html>
            """,
            status_code=200,
        )

    except Exception as e:
        logger.exception("Error during Yandex OAuth callback: %s", e)

        storage_new = env.models.attachment_storage(
            yandex_auth_state="failed",
            yandex_verify_code=None,
        )
        await storage.update(payload=storage_new)

        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Authorization Error</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>An error occurred during authorization: {str(e)}</p>
                <p><a href="/attachments_storage/{storage.id}">Return to storage settings</a></p>
            </body>
            </html>
            """,
            status_code=500,
        )


@router_public.get("/auth/{storage_id}")
async def oauth2_start(req: Request, storage_id: int):
    """
    Начинает процесс OAuth2 авторизации для Яндекс.Диска.

    Возвращает authorization_url для редиректа на oauth.yandex.ru.

    Path parameters:
    - storage_id: ID storage для авторизации
    """
    env: "Environment" = req.app.state.env

    storage_list = await env.models.attachment_storage.search(
        filter=[
            ("id", "=", storage_id),
            ("type", "=", "yandex"),
        ],
        limit=1,
        fields=[
            "id",
            "name",
            "yandex_client_id",
            "yandex_client_secret",
        ],
    )

    if not storage_list:
        return JSONResponse(
            content={"error": "Storage not found"},
            status_code=404,
        )

    storage = storage_list[0]

    if not (storage.yandex_client_id and storage.yandex_client_secret):
        return JSONResponse(
            content={
                "error": "Please fill in Client ID and Client Secret first"
            },
            status_code=400,
        )

    try:
        # Генерируем verify_code (state)
        verify_code = secrets.token_urlsafe(32)

        # Сохраняем verify_code
        storage_new = env.models.attachment_storage(
            yandex_verify_code=verify_code,
            yandex_auth_state="pending",
        )
        await storage.update(payload=storage_new)

        api_url = await env.models.system_settings.get_api_url()
        api_url = _normalize_api_url(api_url)
        redirect_uri = f"{api_url}/yandex/callback"

        params = {
            "response_type": "code",
            "client_id": storage.yandex_client_id,
            "redirect_uri": redirect_uri,
            "state": verify_code,
            "force_confirm": "yes",
        }

        authorization_url = f"{YANDEX_AUTHORIZE_URL}?{urlencode(params)}"

        logger.info("Generated Yandex OAuth URL for storage %s", storage_id)

        return JSONResponse(
            content={"authorization_url": authorization_url},
            status_code=200,
        )

    except Exception as e:
        logger.exception("Error generating Yandex OAuth URL: %s", e)
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
        )
