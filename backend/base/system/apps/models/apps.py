"""
Реестр приложений — строка на каждое приложение из project_setup (Apps).

На него ссылаются роли (группировка по приложениям) и «Рабочие места».
Заполняет его модуль apps — App.seed в своём post_init (sequence 0,
раньше остальных модулей). Флаг «установлено» добавляет модуль
apps_install (@extend).
"""

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import Boolean, Char, Integer
from backend.base.system.dotorm.dotorm.model import DotModel

if TYPE_CHECKING:
    from backend.base.system.core.apps import AppsCore


class App(DotModel):
    """
    Приложение/модуль системы (строка на каждое приложение из Apps).

    Используется для группировки ролей по приложениям и «Рабочих мест».
    """

    __table__ = "apps"

    id: int = Integer(primary_key=True)
    code: str = Char(max_length=64, unique=True)
    name: str = Char(max_length=128)
    active: bool = Boolean(default=True)
    sequence: int = Integer(default=10, description="Порядок в очереди")

    # Признак «UI-приложение»: модуль даёт плитку главного меню (лаунчера).
    # Объявляется в info САМОГО МОДУЛЯ ("ui_menu": True, "ui_menu_name": "…");
    # App.seed переносит их на строку App. Список UI-приложений — запрос
    # App где ui_menu=true (не хардкод-список).
    ui_menu: bool = Boolean(
        default=False, description="Модуль даёт плитку главного меню"
    )
    # Ключ группы меню на фронте (communication, crm, settings, telephony, …).
    # Именно он — контракт с фронтом; App.code остаётся кодом МОДУЛЯ (chat,
    # leads, security, chat_phone). «Рабочее место» ссылается на App через
    # app_ids (m2m), фронту отдаётся набор ui_menu_name.
    ui_menu_name: str | None = Char(
        max_length=64,
        required=False,
        description="Ключ группы меню на фронте (контракт)",
    )

    @classmethod
    async def seed(cls, apps: "AppsCore") -> None:
        """Создаёт/обновляет записи для всех приложений (идемпотентно).

        Каждый модуль может объявить у себя атрибуты ui_menu / ui_menu_name
        — тогда его строка становится «UI-приложением» (плиткой лаунчера).
        Флаги переносятся сюда и для НОВЫХ, и для уже существующих строк,
        чтобы после обновления кода объявления подхватывались без
        пересоздания apps.
        """
        app_codes = apps.get_names()

        if not app_codes:
            return

        exist_apps = await cls.search(
            filter=[("code", "in", app_codes)],
            fields=["id", "code"],
        )
        exist_by_code = {a.code: a for a in exist_apps}

        for code in app_codes:
            app_instance = apps.get(code)
            info = getattr(app_instance, "info", None) or {}
            name = info.get("name", code)
            ui_menu = bool(info.get("ui_menu", False))
            ui_menu_name = info.get("ui_menu_name")

            existing = exist_by_code.get(code)
            if existing is None:
                await cls.create(
                    payload=cls(
                        code=code,
                        name=name,
                        ui_menu=ui_menu,
                        ui_menu_name=ui_menu_name,
                    )
                )
                continue

            changed = {}
            # Обновляем ТОЛЬКО UI-флаги у объявленных приложений; имя и
            # прочее у существующих строк не трогаем.
            if ui_menu or ui_menu_name:
                changed.update(ui_menu=ui_menu, ui_menu_name=ui_menu_name)
            if changed:
                await existing.update(payload=cls(**changed))
