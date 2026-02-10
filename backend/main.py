"""FARA CRM — FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from backend.project_info import DESCRIPTION, TAGS_METADATA, TITLE, VERSION
from backend.project_setup import env


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.env = env
    await env.setup_services()
    await env.start_services_before(app)
    await env.load_routers(app)
    await env.start_services_after(app)
    await env.start_post_init(app)
    yield
    # shutdown
    await env.stop_services(app)


app = FastAPI(
    title=TITLE,
    description=DESCRIPTION,
    version=VERSION,
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    responses={
        HTTP_200_OK: {"description": "успешно"},
        HTTP_400_BAD_REQUEST: {"description": "ошибка клиента"},
        HTTP_404_NOT_FOUND: {"description": "запись не найдена"},
        HTTP_403_FORBIDDEN: {"description": "ошибка аутентификации"},
        HTTP_422_UNPROCESSABLE_ENTITY: {"description": "ошибка валидации"},
        HTTP_500_INTERNAL_SERVER_ERROR: {"description": "ошибка сервера"},
    },
)


# для обработки JS запросов отправленных с другого источника
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def add_cors(_request: Request, response: JSONResponse) -> JSONResponse:
    """
    CORS headers are not automatically added to error handlers with FastAPI
    cf. https://github.com/fastapi/fastapi/discussions/8027
    """
    cors_headers = {
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Origin": "*",
    }

    response.headers.update(cors_headers)
    return response


env.add_handlers_errors(app)
