"""
AuditMixin — добавляет audit-поля ко всем моделям наследующим его:
- create_user_id    — кто создал
- create_datetime   — когда создал
- update_user_id    — кто последний обновил
- update_datetime   — когда последний раз обновил

create_user_id и create_datetime заполняются default-функциями при первом
создании. update_user_id и update_datetime обновляются автоматически
override'нутым update() — каждый вызов update проставит текущего юзера
и время.

Использование:
    class Partner(AuditMixin, DotModel):
        ...

ВАЖНО: AuditMixin должен идти ПЕРЕД DotModel в списке базовых классов,
иначе override update() не сработает (DotModel уже определит свой).

Для моделей где НЕ нужен audit (User — рекурсивная ссылка, Role,
Language и другие системные) — просто не наследовать AuditMixin.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import Many2one, Datetime
from backend.base.system.dotorm.dotorm.access import get_access_session
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.system.dotorm.dotorm.model import DotModel

    _Base = DotModel
else:
    _Base = object


def _default_current_user():
    session = get_access_session()
    return session.user_id if session else None


def _default_now():
    """Default для *_datetime: текущее UTC время."""
    return datetime.now(timezone.utc)


class AuditMixin(_Base):
    """
    Миксин с audit-полями. Наследуется ПЕРЕД DotModel:

        class Partner(AuditMixin, DotModel):
            ...
    """

    create_user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        default=_default_current_user,
        required=False,
        description="Кто создал запись",
    )

    create_datetime: datetime = Datetime(
        default=_default_now,
        required=False,
        description="Когда создана запись (UTC)",
    )

    update_user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        default=_default_current_user,
        required=False,
        description="Кто последний обновил запись",
    )

    update_datetime: datetime = Datetime(
        default=_default_now,
        required=False,
        description="Когда последний раз обновлена запись (UTC)",
    )

    async def update(self, payload, fields=None, session=None):
        """
        Override DotModel.update — автоматически проставляет
        update_user_id и update_datetime в payload перед записью в БД.

        Если юзер явно передал эти поля в payload — НЕ перезаписываем
        (например для импорта/миграции с сохранением исходных значений).
        """
        access_session = get_access_session()
        current_user_id = access_session.user_id if access_session else None

        # update_user_id — если в payload не передан явно
        if not payload.update_user_id and current_user_id is not None:
            payload.update_user_id = current_user_id

        # update_datetime — если в payload не передан явно
        if not payload.update_datetime:
            payload.update_datetime = _default_now()

        return await super().update(payload, fields=fields, session=session)
