# Copyright 2025 FARA CRM
# Attachments Google Drive module - OAuth2 callback router

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

# Google OAuth2 scopes
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]

router_public = APIRouter(
    tags=["Attachments Google OAuth"],
    prefix="/attachments/google",
)


def credentials_to_dict(credentials) -> dict:
    """Конвертирует credentials объект в словарь для сохранения."""
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else [],
    }


@router_public.get("/callback")
async def oauth2_callback(req: Request):
    """
    OAuth2 callback endpoint для Google Drive.

    Google перенаправляет сюда после авторизации пользователя.
    Получает authorization code и обменивает на access/refresh токены.

    Query parameters:
    - code: Authorization code от Google
    - state: Verification code для поиска storage записи
    - error: Ошибка авторизации (если есть)
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        logger.error("google_auth_oauthlib not installed")
        return HTMLResponse(
            content="""
            <html>
            <head><title>Error</title></head>
            <body>
                <h1>Configuration Error</h1>
                <p>Google Auth library not installed. Please install google-auth-oauthlib.</p>
            </body>
            </html>
            """,
            status_code=500,
        )

    # Проверяем наличие параметра state
    state = req.query_params.get("state")
    if not state:
        logger.warning("OAuth callback called without state parameter")
        return RedirectResponse(url="/")

    # Проверяем ошибку авторизации
    error = req.query_params.get("error")
    if error:
        error_description = req.query_params.get(
            "error_description", "Unknown error"
        )
        logger.error(f"OAuth error: {error} - {error_description}")
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

    env: "Environment" = req.app.state.env

    # Ищем storage по verify_code
    storage_list = await env.models.attachment_storage.search(
        filter=[
            ("type", "=", "google"),
            ("google_verify_code", "=", state),
        ],
        limit=1,
        fields=[
            "id",
            "name",
            "google_json_credentials",
            "google_verify_code",
        ],
    )

    if not storage_list:
        logger.warning(f"Storage not found for state: {state}")
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

    # Получаем credentials из JSON файла
    if not storage.google_json_credentials:
        logger.error(f"No credentials file for storage {storage.id}")
        return HTMLResponse(
            content="""
            <html>
            <head><title>Error</title></head>
            <body>
                <h1>Configuration Error</h1>
                <p>No credentials.json file uploaded for this storage.</p>
                <p><a href="/">Return to main page</a></p>
            </body>
            </html>
            """,
            status_code=400,
        )

    try:
        # Декодируем credentials.json
        credentials_json = storage.google_json_credentials

        # Создаём flow с state
        flow = InstalledAppFlow.from_client_config(
            credentials_json,
            scopes=SCOPES,
            state=storage.google_verify_code,
        )

        # Определяем redirect_uri
        base_url = str(req.base_url).rstrip("/")
        redirect_uri = f"{base_url}/attachments/google/callback"

        # Приводим к HTTPS если не localhost
        if (
            redirect_uri.startswith("http:")
            and "localhost" not in redirect_uri
            and "127.0.0.1" not in redirect_uri
        ):
            redirect_uri = "https:" + redirect_uri[5:]

        flow.redirect_uri = redirect_uri

        # Получаем URL запроса
        authorization_response = str(req.url)

        # Приводим к HTTPS если не localhost
        if (
            authorization_response.startswith("http:")
            and "localhost" not in authorization_response
            and "127.0.0.1" not in authorization_response
        ):
            authorization_response = "https:" + authorization_response[5:]

        logger.info(f"Fetching token with redirect_uri: {redirect_uri}")

        # Обмениваем code на токены
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials

        # Определяем статус авторизации
        if credentials.refresh_token:
            auth_state = "authorized"
        else:
            # Нет refresh_token - возможно повторная авторизация
            auth_state = "authorized"
            logger.warning(
                f"No refresh_token received for storage {storage.id}. "
                "This may happen on re-authorization."
            )

        # Сохраняем credentials в storage
        storage_new = env.models.attachment_storage(
            google_credentials=json.dumps(credentials_to_dict(credentials)),
            google_refresh_token=credentials.refresh_token,
            google_auth_state=auth_state,
            google_verify_code=None,  # Очищаем использованный код
        )
        await storage.update(payload=storage_new)

        logger.info(
            f"Google Drive authorized successfully for storage {storage.id}"
        )

        # Редирект обратно на форму storage
        # Формат URL зависит от фронтенда
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>Authorization Successful</title>
                <script>
                    // Пытаемся закрыть окно или редиректим
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
                <p>Google Drive has been connected successfully.</p>
                <p>You can close this window or <a href="/attachments_storage/{storage.id}">return to storage settings</a>.</p>
            </body>
            </html>
            """,
            status_code=200,
        )

    except Exception as e:
        logger.exception(f"Error during OAuth callback: {e}")

        storage_new = env.models.attachment_storage(
            google_auth_state="failed",
            google_verify_code=None,  # Очищаем использованный код
        )
        # Обновляем статус на failed
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
    Начинает процесс OAuth2 авторизации для Google Drive.

    Генерирует verify_code, сохраняет в storage и редиректит на Google.

    Path parameters:
    - storage_id: ID storage для авторизации
    """
    import secrets

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return HTMLResponse(
            content="<h1>Error</h1><p>google-auth-oauthlib not installed</p>",
            status_code=500,
        )

    env: "Environment" = req.app.state.env

    # Получаем storage
    storage_list = await env.models.attachment_storage.search(
        filter=[
            ("id", "=", storage_id),
            ("type", "=", "google"),
        ],
        limit=1,
        fields=[
            "id",
            "name",
            "google_json_credentials",
        ],
    )

    if not storage_list:
        return HTMLResponse(
            content="<h1>Error</h1><p>Storage not found</p>",
            status_code=404,
        )

    storage = storage_list[0]

    if not storage.google_json_credentials:
        return HTMLResponse(
            content="<h1>Error</h1><p>Please upload credentials.json first</p>",
            status_code=400,
        )

    try:
        # Декодируем credentials.json
        credentials_json = storage.google_json_credentials

        # Генерируем verify_code
        verify_code = secrets.token_urlsafe(32)

        # Сохраняем verify_code
        storage_new = env.models.attachment_storage(
            google_verify_code=verify_code, google_auth_state="pending"
        )
        await storage.update(
            payload=storage_new,
        )

        # Создаём flow
        flow = InstalledAppFlow.from_client_config(
            credentials_json,
            scopes=SCOPES,
            state=verify_code,
        )

        # Определяем redirect_uri
        base_url = str(req.base_url).rstrip("/")
        redirect_uri = f"{base_url}/attachments/google/callback"

        # Приводим к HTTPS если не localhost
        if (
            redirect_uri.startswith("http:")
            and "localhost" not in redirect_uri
            and "127.0.0.1" not in redirect_uri
        ):
            redirect_uri = "https:" + redirect_uri[5:]

        flow.redirect_uri = redirect_uri

        # Генерируем URL авторизации
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # Всегда запрашиваем consent для получения refresh_token
        )

        logger.info(f"Redirecting to Google OAuth: {authorization_url}")

        return RedirectResponse(url=authorization_url)

    except Exception as e:
        logger.exception(f"Error starting OAuth: {e}")
        return HTMLResponse(
            content=f"<h1>Error</h1><p>{str(e)}</p>",
            status_code=500,
        )
