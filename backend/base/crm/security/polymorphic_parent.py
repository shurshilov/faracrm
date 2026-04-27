# Copyright 2025 FARA CRM
# Security — PolymorphicParentMixin
#
# При удалении записи каскадно удаляет связанные polymorphic-children
# (attachments, activities) у которых res_model + res_id указывают на эту запись.
#
# Поведение: сначала удаляется сам parent, потом children.
# Если удаление children упало — warning в лог, parent уже удалён.

import logging
from typing import ClassVar

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from ...system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.access import (
    get_access_session,
    set_access_session,
)
from backend.base.crm.security.models.sessions import SystemSession

logger = logging.getLogger(__name__)


class PolymorphicParentMixin(DotModel):
    """
    Mixin для моделей которые могут быть parent для polymorphic children
    (attachments, activities, и т.п. — модели с res_model + res_id).

    При удалении записи каскадно удаляет всех её polymorphic children.

    Использование:
        class Partner(PolymorphicParentMixin, DotModel):
            __table__ = "partners"

    Можно переопределить список children-моделей:
        class MyModel(PolymorphicParentMixin, DotModel):
            __polymorphic_children__ = [
                ("attachment", "res_model", "res_id"),
                ("activity", "res_model", "res_id"),
                ("custom_log", "object_type", "object_id"),  # своя модель
            ]
    """

    # Список (child_model_name, model_field, id_field)
    __polymorphic_children__: ClassVar[list[tuple[str, str, str]]] = [
        ("attachment", "res_model", "res_id"),
        ("activity", "res_model", "res_id"),
    ]

    async def delete(self, session=None):
        # Сначала удаляем сам parent — если упадёт, дальше не пойдём.
        # Это правильный порядок: удалить родителя приоритетно, children
        # каскадятся как best-effort.
        cls = self.__class__
        parent_id = self.id
        result = await super().delete(session=session)

        # Parent удалён успешно — каскадим children. Не падаем если
        # что-то идёт не так: parent уже удалён, мусор почистится позже.
        await cls._delete_polymorphic_children([parent_id], session=session)
        return result

    @hybridmethod
    async def delete_bulk(self, ids: list[int], session=None):
        cls = self.__class__
        result = await super().delete_bulk(ids, session=session)
        await cls._delete_polymorphic_children(ids, session=session)
        return result

    @classmethod
    async def _delete_polymorphic_children(
        cls, parent_ids: list[int], session=None
    ):
        """
        Удалить все polymorphic-children (attachments, activities, ...)
        привязанные к parent_ids.

        Best-effort: ошибка на одной модели не мешает другим.

        ВАЖНО: используем SystemSession для обхода rules. Это нужно
        по двум причинам:
          1. После удаления parent его children становятся "orphan'ами" —
             rules @has_polymorphic_parent_access вернут пустой список,
             и search не найдёт что удалять.
          2. У юзера может не быть delete-прав на attachment (мы их
             закрыли через ACL). Но cascade — это системная операция,
             и она должна работать независимо от прав юзера.
        """

        table_name = cls.__table__

        # Сохраняем текущую сессию, переключаемся на SystemSession
        prev_session = get_access_session()
        # SystemSession требует user_id, но в рамках cascade достаточно
        # любого валидного — sysadmin id=1 (создаётся первым в системе).
        # Если в твоей системе другой id — поправь или передай явно.
        try:
            from ..users.models.users import SYSTEM_USER_ID

            sys_session = SystemSession(user_id=SYSTEM_USER_ID)
        except Exception:
            # Fallback: если SystemSession сейчас недоступна — пробуем
            # как есть с текущей сессией.
            sys_session = prev_session

        set_access_session(sys_session)
        try:
            for child_info in cls.__polymorphic_children__:
                child_model_name, model_field, id_field = child_info

                child_cls = getattr(env.models, child_model_name, None)
                if child_cls is None:
                    logger.debug(
                        "PolymorphicParentMixin: child model '%s' not found",
                        child_model_name,
                    )
                    continue

                try:
                    children = await child_cls.search(
                        filter=[
                            (model_field, "=", table_name),
                            (id_field, "in", parent_ids),
                        ],
                        fields=["id"],
                    )
                    if not children:
                        continue

                    child_ids = [c.id for c in children]
                    # delete_bulk у Attachment имеет свой кастомный код
                    # для удаления физических файлов из storage.
                    await child_cls.delete_bulk(child_ids, session=session)

                    logger.info(
                        "PolymorphicParentMixin: deleted %d %s for %s ids=%s",
                        len(child_ids),
                        child_model_name,
                        table_name,
                        parent_ids,
                    )
                except Exception as e:
                    logger.warning(
                        "PolymorphicParentMixin: failed to delete %s "
                        "children for %s ids=%s: %s",
                        child_model_name,
                        table_name,
                        parent_ids,
                        e,
                    )
        finally:
            # Восстанавливаем исходную сессию
            set_access_session(prev_session)
