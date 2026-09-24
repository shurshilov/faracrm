# Copyright 2025 FARA CRM
# Marketplace module - отзыв о приложении

from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.access import get_access_session
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import Integer, Many2one, Text
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.base.crm.marketplace.models.marketplace_app import (
        MarketplaceApplication,
    )


def _review_error(content: str, detail: str) -> FaraException:
    return FaraException(
        {"content": content, "detail": detail, "status_code": 400}
    )


class MarketplaceReview(AuditMixin, DotModel):
    """
    Отзыв о приложении: оценка 1–5 и текст, автор — create_user_id.

    Оставляет вошедший пользователь: один раз на приложение, только об
    опубликованном и не о своём. Править и удалять — администратор.
    """

    __table__ = "marketplace_review"

    id: int = Integer(primary_key=True)
    app_id: "MarketplaceApplication" = Many2one(
        relation_table=lambda: env.models.marketplace_app,
        required=True,
        index=True,
        ondelete="cascade",
        description="Приложение",
    )
    rating: int = Integer(description="Оценка, 1–5")
    text: str | None = Text(description="Отзыв")

    @hybridmethod
    async def create(self, payload, session=None, depends_jobs=None):
        if not payload.rating or not 1 <= payload.rating <= 5:
            raise _review_error(
                "MARKETPLACE_REVIEW_RATING", "Поставьте оценку от 1 до 5"
            )
        app_id = getattr(payload.app_id, "id", payload.app_id)
        # Правило каталога «опубликовано или своё»: чужое неопубликованное
        # приложение сессия и так не найдёт.
        app = await env.models.marketplace_app.search_one(
            filter=[("id", "=", app_id)],
            fields=["id", "published", "create_user_id"],
        )
        if not app or not app.published:
            raise _review_error(
                "MARKETPLACE_APP_NOT_PUBLISHED", "Приложение не опубликовано"
            )
        user_id = get_access_session().user_id.id
        if app.create_user_id and app.create_user_id.id == user_id:
            raise _review_error(
                "MARKETPLACE_REVIEW_OWN_APP",
                "Нельзя оставить отзыв о своём приложении",
            )
        if await self.exists(
            filter=[("app_id", "=", app_id), ("create_user_id", "=", user_id)]
        ):
            raise _review_error(
                "MARKETPLACE_REVIEW_EXISTS",
                "Вы уже оставили отзыв об этом приложении",
            )
        return await super().create(payload, session, depends_jobs)
