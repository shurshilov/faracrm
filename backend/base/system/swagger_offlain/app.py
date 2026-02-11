import functools
import io
import logging
from os import path
from fastapi import Response
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
)
import yaml

from backend.base.system.core.service import Service

LOG = logging.getLogger(__package__)


class SwaggerOfflainService(Service):
    """
    Сервис который добавляет оффлайн документацию
    """

    info = {
        "name": "App swagger offline docs",
        "summary": "Swagger offline docs",
        "author": "Artem Shurshilov",
        "category": "Base",
        "version": "1.0.0",
        "license": "MIT",
        "depends": [],
        "service": True,
    }

    async def startup(self, app) -> None:
        """Старт сервиса"""
        app.mount(
            "/base/swagger_offlain/static",
            StaticFiles(
                directory=path.abspath(path.dirname(__file__)) + "/static"
            ),
            name="swagger_offlain",
        )

        @app.get("/docs", include_in_schema=False)
        async def swagger_ui_html():
            return get_swagger_ui_html(
                openapi_url=app.openapi_url or "",
                title=app.title + " - Swagger UI",
                swagger_js_url="/base/swagger_offlain/static/swagger-ui-bundle.js",
                swagger_css_url="/base/swagger_offlain/static/swagger-ui.css",
            )

        @app.get("/redoc", include_in_schema=False)
        async def redoc_html():
            return get_redoc_html(
                openapi_url=app.openapi_url or "",
                title=app.title + " - ReDoc",
                redoc_js_url="/base/swagger_offlain/static/redoc.standalone.js",
            )

        # add endpoints
        # additional yaml version of openapi.json
        @app.get("/api/openapi.yaml", include_in_schema=False)
        @functools.lru_cache()
        def read_openapi_yaml() -> Response:
            openapi_json = app.openapi()
            yaml_s = io.StringIO()
            yaml.dump(openapi_json, yaml_s, allow_unicode=True)
            return Response(yaml_s.getvalue(), media_type="text/yaml")

    async def shutdown(self, app):
        """Отключение сервиса"""
        ...
