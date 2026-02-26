"""Developer documentation — serves MkDocs static site on /docs-dev."""

import os
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.base.system.core.service import Service

logger = logging.getLogger(__name__)

# docs/site/ relative to project root
DOCS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",  # → project root
    "docs",
    "site",
)
DOCS_DIR = os.path.normpath(DOCS_DIR)


class DocsApp(Service):
    """Отдаёт собранную MkDocs-документацию как статику."""

    info = {
        "name": "Developer Docs",
        "service": True,
        "summary": "Developer Docs",
        "author": "Artem Shurshilov",
        "category": "Base",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "cron_skip": True,
    }

    async def startup(self, app: FastAPI):
        await super().startup(app)

        if not os.path.isdir(DOCS_DIR):
            logger.warning(
                "DocsApp: directory %s not found — "
                "run 'mkdocs build' first. Docs will not be served.",
                DOCS_DIR,
            )
            return

        app.mount(
            "/docs-dev",
            StaticFiles(directory=DOCS_DIR, html=True),
            name="docs_developer",
        )

        logger.info("DocsApp: serving docs at /docs-dev")

    async def shutdown(self, app: FastAPI):
        pass
