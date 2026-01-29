# Copyright 2025 FARA CRM
# Attachments Google Drive module - OAuth2 callback router

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse

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
    prefix="/google",
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
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
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
        # Получаем credentials.json (уже dict)
        credentials_json = storage.google_json_credentials

        # Создаём flow с state
        flow = InstalledAppFlow.from_client_config(
            credentials_json,
            scopes=SCOPES,
            state=storage.google_verify_code,
        )

        # Определяем redirect_uri
        base_url = str(req.base_url).rstrip("/")
        if base_url.startswith(r"http://127.0.0.1"):
            base_url = "http://localhost" + base_url[16:]

        # Приводим к HTTPS если не localhost
        elif base_url.startswith("http:") and "localhost" not in base_url:
            base_url = "https:" + base_url[5:]

        redirect_uri = f"{base_url}/google/callback"

        flow.redirect_uri = redirect_uri

        # Получаем URL запроса
        authorization_response = str(req.url)

        # Приводим к HTTPS если не localhost
        if (
            authorization_response.startswith("http:")
            and "localhost" not in authorization_response
        ):
            authorization_response = "https:" + authorization_response[5:]

        logger.info(f"Fetching token with redirect_uri: {redirect_uri}")

        # Use the authorization server's response to fetch the OAuth 2.0 tokens.
        # Add HTTPS for localhost test
        if authorization_response.startswith("http:"):
            authorization_response = "https:" + authorization_response[5:]
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

    Возвращает authorization_url для редиректа на Google.

    Path parameters:
    - storage_id: ID storage для авторизации
    """
    import secrets

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return JSONResponse(
            content={"error": "google-auth-oauthlib not installed"},
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
        return JSONResponse(
            content={"error": "Storage not found"},
            status_code=404,
        )

    storage = storage_list[0]

    if not storage.google_json_credentials:
        return JSONResponse(
            content={"error": "Please upload credentials.json first"},
            status_code=400,
        )

    try:
        # Получаем credentials.json (уже dict)
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
        if base_url.startswith(r"http://127.0.0.1"):
            base_url = "http://localhost" + base_url[16:]

        # Приводим к HTTPS если не localhost
        elif base_url.startswith("http:") and "localhost" not in base_url:
            base_url = "https:" + base_url[5:]
            # raise ValueError(
            #     f"Please check, that system parameter web.base.url, \
            #     should start 'HTTPS://' or be localhost (example - http://127.0.0.1:8069). \
            #     Current web.base.url: {base_url}"
            # )

        flow.redirect_uri = f"{base_url}/google/callback"

        # Генерируем URL авторизации
        authorization_url, state = flow.authorization_url(
            # Enable offline access so that you can refresh an access token without
            # re-prompting the user for permission. Recommended for web server apps.
            access_type="offline",
            # Optional, set prompt to 'consent' will prompt the user for consent
            # always request consent, for always get refresh token
            prompt="consent",
            # Enable incremental authorization. Recommended as a best practice.
            # Disable for none-check scopes on callback
            # include_granted_scopes="true",
        )

        logger.info(f"Generated Google OAuth URL for storage {storage_id}")

        return JSONResponse(
            content={"authorization_url": authorization_url},
            status_code=200,
        )

    except Exception as e:
        logger.exception(f"Error generating OAuth URL: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
        )
