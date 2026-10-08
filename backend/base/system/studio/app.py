"""
Студия: поля, которые администратор настроек добавляет к моделям из
интерфейса (меню «⋮ → Поля модели…»).

Источник истины — таблица studio_fields, значения — обычные колонки
таблиц моделей. Сервис стартует до автокруда: вешает поля на модели
(DotModel.add_fields + аннотация) и добавляет колонки штатным DDL-синком,
так что схемы API и роуты строятся уже с ними.

Сервис отключаемый и по умолчанию выключен: стартует, только когда
установлен (страница /apps). Удаление зовёт shutdown — поля снимаются с
моделей; колонки и строки studio_fields остаются, повторная установка
вернёт всё. Схемы автокруда студия пересобирает сама, если он уже запущен
— то есть только при установке и удалении на ходу: на старте процесса
автокруд стартует позже студии, при остановке — останавливается раньше.

Изменение в работающей системе — роутер studio: строка и колонка, затем
refresh → rebuild в своём воркере и studio_changed в шину; остальные
воркеры и крон приводят модели к таблице в sync — на событие студия
подписывается сама при старте (env.apps.bus.subscribe).
"""

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.base.crm.security.acl_post_init_mixin import ACL
from backend.base.system.core.enviroment import env
from backend.base.system.core.service import Service
from backend.base.system.dotorm.dotorm.access import (
    get_access_session,
    set_access_session,
)
from backend.base.system.dotorm.dotorm.fields import Field

if TYPE_CHECKING:
    from fastapi import FastAPI


@contextmanager
def _system_session():
    """Старт и событие шины: системная сессия в контексте, как у
    post_init (Environment.start_post_init). Без сессии ORM отказывает
    (default-deny), .sudo() сессию не заменяет. Старт бывает и внутри
    запроса установки — его сессию после возвращаем."""
    from backend.base.crm.security.models.sessions import SystemSession
    from backend.base.crm.users.models.users import SYSTEM_USER_ID

    previous = get_access_session()
    set_access_session(SystemSession(user_id=SYSTEM_USER_ID))
    try:
        yield
    finally:
        set_access_session(previous)


def _without(raw: str | None, name: str) -> str | None:
    """JSON-массив имён без name; без вхождения — как было."""
    names = json.loads(raw or "[]")
    if name not in names:
        return raw
    return json.dumps([item for item in names if item != name])


def _without_cell(raw: str | None, name: str) -> str | None:
    """JSON-массив клеток зоны без клетки поля name; без неё — как было."""
    cells = json.loads(raw or "[]")
    kept = [cell for cell in cells if cell["name"] != name]
    if len(kept) == len(cells):
        return raw
    return json.dumps(kept)


class StudioApp(Service):
    """Поля моделей из интерфейса."""

    info = {
        "name": "Studio",
        "summary": "Model fields from the UI, no code",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "service": True,
        # Отключаемый, по умолчанию выключен — ставит администратор.
        "core": False,
        "auto_install": False,
        # После load_routers (флаги установки прочитаны) и до автокруда
        # (sequence 10), который строит схемы уже с полями студии.
        "sequence": 5,
        "post_init": True,
    }

    BASE_USER_ACL = {
        # Настройки формы применяет каждая форма — читают все, меняет
        # администратор настроек (ROLE_ACL ниже).
        "form_setting": ACL.READ_ONLY,
    }

    ROLE_ACL = {
        "system_admin": {
            "studio_field": ACL.FULL,
            "form_setting": ACL.FULL,
        },
    }

    def __init__(self) -> None:
        super().__init__()
        # Поля, применённые в этом процессе: (таблица, имя) → id строки.
        self._applied: dict[tuple[str, str], int] = {}

    async def startup(self, app: "FastAPI") -> None:
        await super().startup(app)
        with _system_session():
            added, _ = await self.refresh()
        if added:
            await env.apps.db.sync_tables(added)
            await self.rebuild(app)
        # Поле добавили/удалили в другом воркере — привести модели здесь.
        env.apps.bus.subscribe("studio_changed", lambda event: self.sync(app))

    async def shutdown(self, app: "FastAPI") -> None:
        """Студию удалили (или процесс останавливается): отписаться от
        шины, снять её поля с моделей и пересобрать схемы автокруда."""
        env.apps.bus.unsubscribe("studio_changed")
        if self._detach(list(self._applied)):
            await self.rebuild(app)
        await super().shutdown(app)

    def _detach(self, keys: list[tuple[str, str]]) -> list[type]:
        """Снять применённые поля (таблица, имя) с моделей; модели, у
        которых что-то снято."""
        removed: dict[type, list[str]] = {}
        for key in keys:
            model = env.models._get_model_class_by_table(key[0])
            removed.setdefault(model, []).append(key[1])
            del self._applied[key]
        for model, names in removed.items():
            model.remove_fields(names)
        return list(removed)

    async def refresh(self) -> tuple[list[type], list[type]]:
        """Привести поля моделей к таблице studio_fields.

        Возвращает модели, получившие новые поля, и модели, у которых поля
        убраны. Колонки не трогает: на старте и в роутере их добавляет
        db.sync_tables; при удалении поля колонка с данными остаётся.
        """
        rows = await env.models.studio_field.sudo().search(
            fields=[
                "id",
                "model_name",
                "name",
                "label",
                "field_type",
                "options",
                "relation_model",
            ]
        )
        current = {(row.model_name, row.name): row for row in rows}

        added: dict[type, dict[str, Field]] = {}
        annotations: dict[type, dict[str, object]] = {}
        for key, row in current.items():
            model = env.models._get_model_class_by_table(row.model_name)
            if key in self._applied:
                # Подпись и варианты правятся на месте: в схемы API они
                # не входят, пересборка не нужна.
                field = model.get_fields()[row.name]
                field.string = row.label
                if row.field_type == "selection":
                    field.options = row._options(row.options)
                continue
            field, annotation = row.build()
            added.setdefault(model, {})[row.name] = field
            annotations.setdefault(model, {})[row.name] = annotation
            self._applied[key] = row.id

        for model, fields in added.items():
            model.add_fields(fields)
            # Аннотации — как у @extend: по ним генератор схем типизирует
            # поле, без них оно было бы Any.
            merged = dict(getattr(model, "__annotations__", {}))
            merged.update(annotations[model])
            model.__annotations__ = merged
        removed = self._detach(
            [key for key in self._applied if key not in current]
        )

        return list(added), removed

    async def rebuild(self, app: "FastAPI") -> None:
        """Пересобрать схемы и авто-роуты под изменившиеся поля — в этом
        процессе, если автокруд в нём запущен (в кроне его нет, на старте
        процесса он ещё не стартовал, при остановке уже остановлен)."""
        if "dotorm_crud_auto" not in env.running:
            return
        await env.apps.dotorm_crud_auto.rebuild(app, env)

    async def sync(self, app: "FastAPI") -> None:
        """studio_changed из другого воркера (и своё же событие — шина
        доставляет всем): привести модели к таблице и, если что-то
        изменилось, пересобрать схемы и роуты."""
        with _system_session():
            added, removed = await self.refresh()
        if added or removed:
            await self.rebuild(app)

    async def publish(self) -> None:
        """Сообщить остальным воркерам и крону — шина (модуль bus; без
        неё меняется только этот процесс)."""
        await env.apps.bus.publish("studio_changed", {})

    async def show_on_form(self, model_name: str, name: str) -> None:
        """Новое поле сразу на форме: клеткой зоны «Дополнительно» общих
        настроек, без места — встанет в первую свободную клетку; редактор
        студии ставит его в клетку, куда поле бросили."""
        FormSetting = env.models.form_setting
        row = await FormSetting.sudo().search_one(
            filter=[("model_name", "=", model_name)],
            fields=["id", "extra_fields"],
        )
        cells = json.loads(row.extra_fields or "[]") if row else []
        if any(cell["name"] == name for cell in cells):
            return
        extra_fields = json.dumps([*cells, {"name": name}])
        if row:
            await row.sudo().update(FormSetting(extra_fields=extra_fields))
        else:
            await FormSetting.sudo().create(
                FormSetting(model_name=model_name, extra_fields=extra_fields)
            )

    async def forget(self, model_name: str, name: str) -> None:
        """Убрать удалённое поле из общих настроек формы — иначе их
        проверка (@constrains form_setting) отклонит следующее сохранение."""
        rows = await env.models.form_setting.sudo().search(
            filter=[("model_name", "=", model_name)],
            fields=["id", "required", "extra_fields"],
        )
        for row in rows:
            required = _without(row.required, name)
            extra_fields = _without_cell(row.extra_fields, name)
            if (required, extra_fields) == (row.required, row.extra_fields):
                continue
            await row.sudo().update(
                env.models.form_setting(
                    required=required, extra_fields=extra_fields
                )
            )
