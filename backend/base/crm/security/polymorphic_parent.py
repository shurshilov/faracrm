# Copyright 2025 FARA CRM
# Security — PolymorphicParentMixin
#
# При удалении записи каскадно удаляет связанные polymorphic-children
# (attachments, activities, record-чаты) у которых res_model + res_id
# указывают на эту запись.
#
# Поведение: сначала удаляется сам parent, потом children.
# Если удаление children упало — warning в лог, parent уже удалён.
#
# Поля-связи на детей (activity_ids / attachment_ids / note_chat_ids) сюда
# НЕ относятся: их получает КАЖДАЯ модель автоматически из реестра
# (ModelsCore._attach_polymorphic_fields по __polymorphic_field__ детей).

import logging
from typing import ClassVar

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from ...system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

logger = logging.getLogger(__name__)


class PolymorphicParentMixin(DotModel):
    """
    Mixin для моделей, при удалении которых нужно каскадно удалить их
    polymorphic children (модели с res_model + res_id).

    Список детей — из реестра (env.models._polymorphic_children, собран
    по __polymorphic_field__ дочерних моделей); __polymorphic_children__
    переопределяет его для своих моделей с другими именами колонок:

        class MyModel(PolymorphicParentMixin, DotModel):
            __polymorphic_children__ = [
                ("custom_log", "object_type", "object_id"),
            ]
    """

    # Список (child_model_name, model_field, id_field); None — из реестра.
    __polymorphic_children__: ClassVar[list[tuple[str, str, str]] | None] = (
        None
    )

    @classmethod
    def _polymorphic_children(cls) -> list[tuple[str, str, str]]:
        if cls.__polymorphic_children__ is not None:
            return cls.__polymorphic_children__
        return [
            (model_name, "res_model", "res_id")
            for model_name, _field, _filter in env.models._polymorphic_children
        ]

    async def delete(self, session=None, depends_jobs=None):
        # Сначала удаляем сам parent — если упадёт, дальше не пойдём.
        # Это правильный порядок: удалить родителя приоритетно, children
        # каскадятся как best-effort.
        cls = self.__class__
        parent_id = self.id
        result = await super().delete(
            session=session, depends_jobs=depends_jobs
        )

        # Parent удалён успешно — каскадим children. Не падаем если
        # что-то идёт не так: parent уже удалён, мусор почистится позже.
        await cls._delete_polymorphic_children([parent_id], session=session)
        return result

    @hybridmethod
    async def delete_bulk(
        self, ids: list[int], session=None, depends_jobs=None
    ):
        cls = self.__class__
        result = await super().delete_bulk(
            ids, session=session, depends_jobs=depends_jobs
        )
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

        ВАЖНО: поиск и удаление детей — под sudo (пользователь остаётся
        вызывающего). Это нужно по двум причинам:
          1. После удаления parent его children становятся "orphan'ами" —
             rules @has_polymorphic_parent_access вернут пустой список,
             и search не найдёт что удалять.
          2. У юзера может не быть delete-прав на attachment (мы их
             закрыли через ACL). Но cascade — это системная операция,
             и она должна работать независимо от прав юзера.
        """

        table_name = cls.__table__

        for child_info in cls._polymorphic_children():
            child_model_name, model_field, id_field = child_info

            child_cls = getattr(env.models, child_model_name, None)
            if child_cls is None:
                logger.debug(
                    "PolymorphicParentMixin: child model '%s' not found",
                    child_model_name,
                )
                continue

            try:
                children = await child_cls.sudo().search(
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
                await child_cls.sudo().delete_bulk(child_ids, session=session)

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
