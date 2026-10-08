"""
Установка и удаление приложений из интерфейса — без рестарта.

Ядро само умеет одно: поднять приложения из project_setup, все активны.
Этот модуль сужает набор по флагам таблицы apps (App.installed, см.
models/app_ext.py) и меняет его на ходу примитивами ядра:

- старт — сразу после базы и шины, до монтирования роутов и остальных
  сервисов: флаги из БД → env.installed;
- установка: флаг → post_init приложения (сидеры идемпотентны) → его
  роуты и отключаемый сервис в этом процессе, событие apps_changed в шину;
- удаление — только флаг: данные, роли и настройки остаются, роуты
  вырезаются, отключаемый сервис останавливается (shutdown); повторная
  установка возвращает всё как было;
- apps_changed из другого воркера — перечитать флаги, привести процесс.

Ручки и каталог — routers/apps.py, граф зависимостей — graph.py.

Окружение — всегда app.state.env процесса (как раньше у методов
Environment — self), а не модульный env: в тестах это разные объекты.
"""

from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import POST_INIT_LOCK_ID
from backend.base.system.core.service import Service

from .graph import install_order, is_core, uninstall_order

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment


class AppsInstallService(Service):
    """Установка и удаление приложений на ходу."""

    info = {
        "name": "Apps install",
        "summary": "Install and uninstall apps from the UI without restart",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["apps"],
        "service": True,
        "service_start_before": True,
        # После базы (2) и шины (3): флаги читаются до монтирования роутов
        # и старта остальных сервисов.
        "sequence": 4,
        "post_init": True,
    }

    def __init__(self) -> None:
        super().__init__()
        # Флаги, прочитанные на старте: код → установлено. Кодов без
        # строки тут нет — их строки потом создаст модуль apps.
        self._known: dict[str, bool] = {}

    async def startup(self, app: "FastAPI") -> None:
        await super().startup(app)
        env: "Environment" = app.state.env
        self._known = await self.load_installed(env)
        env.apps.bus.subscribe(
            "apps_changed", lambda event: self._on_apps_changed(app)
        )

    async def shutdown(self, app: "FastAPI") -> None:
        """Снимок строк годен, пока сервис запущен: после остановки
        post_init без старта считает новыми все строки."""
        app.state.env.apps.bus.unsubscribe("apps_changed")
        self._known = {}
        await super().shutdown(app)

    async def post_init(self, app: "FastAPI") -> None:
        """Строкам, которые ядро создало новым приложениям с флагом по
        умолчанию, — правило auto_install; core установлено всегда."""
        await super().post_init(app)
        env: "Environment" = app.state.env
        rows = await env.models.app.search(fields=["id", "code", "installed"])
        for row in rows:
            core = is_core(env.apps, row.code)
            want = core or env.is_installed(row.code)
            if row.installed == want:
                continue
            if core or row.code not in self._known:
                await row.update(env.models.app(installed=want))

    async def load_installed(self, env: "Environment") -> dict[str, bool]:
        """Перечитать флаги в env.installed; вернуть прочитанные строки.

        Core — всегда. Со строкой в apps — как в БД. Без строки (первый
        старт, новый модуль в коде) — auto_install из info, по умолчанию
        True. Сырой SQL: на старте ещё нет проверки доступа и сессии.
        """
        db = env.models.app._get_db_session()
        try:
            rows = await db.execute(
                "SELECT code, installed FROM apps", [], cursor="fetch"
            )
        except Exception:
            rows = []  # таблицы ещё нет (sync_db выключен)
        known = {r["code"]: r["installed"] is not False for r in rows}
        env.installed = {
            code
            for code in env.apps.get_names()
            if is_core(env.apps, code)
            or known.get(
                code, env.apps.get(code).info.get("auto_install", True)
            )
        }
        return known

    async def install_apps(
        self, codes: list[str], app: "FastAPI"
    ) -> list[str]:
        """Установить приложения (с недостающими зависимостями).

        Для каждого: флаг installed → post_init (сидеры идемпотентны, это
        тот же код, что на старте). Под sudo и тем же advisory-локом, что и
        стартовые сидеры.
        """
        env: "Environment" = app.state.env
        order = install_order(env.apps, codes, env.installed)
        if not order:
            return []
        async with env.apps.db.advisory_lock(POST_INIT_LOCK_ID):
            for code in order:
                await self._set_installed(env, code, True)
                env.installed.add(code)
                service = env.apps.get(code)
                if service.info.get("post_init"):
                    await service.sudo().post_init(app)
        await self.apps_changed(app)
        return order

    async def uninstall_apps(
        self, codes: list[str], app: "FastAPI"
    ) -> list[str]:
        """Удалить приложения вместе с установленными зависимыми.

        Только флаг. Таблицы, роли, ACL и настройки не трогаем: роуты
        вырезаются, меню прячется, а повторная установка возвращает всё
        без потерь.
        """
        env: "Environment" = app.state.env
        order = uninstall_order(env.apps, codes, env.installed)
        if not order:
            return []
        for code in order:
            await self._set_installed(env, code, False)
            env.installed.discard(code)
        await self.apps_changed(app)
        return order

    async def _set_installed(
        self, env: "Environment", code: str, value: bool
    ) -> None:
        """Флаг installed — под sudo: ставит его админ из интерфейса, ACL на
        apps у его ролей может не быть."""
        row = await env.models.app.sudo().search_one(
            filter=[("code", "=", code)], fields=["id"]
        )
        if row:
            await row.sudo().update(payload=env.models.app(installed=value))

    async def apps_changed(self, app: "FastAPI") -> None:
        """Флаги изменились: свой процесс — сразу, остальным воркерам и
        крону — событие в шину. Без шины меняется только этот процесс."""
        await self.apply_installed(app)
        await app.state.env.apps.bus.publish("apps_changed", {})

    async def _on_apps_changed(self, app: "FastAPI") -> None:
        """apps_changed из шины (и своё же — шина доставляет и
        отправителю): перечитать флаги и привести к ним процесс."""
        await self.load_installed(app.state.env)
        await self.apply_installed(app)

    async def apply_installed(self, app: "FastAPI") -> None:
        """Привести процесс к env.installed: роуты и отключаемые
        сервисы."""
        self.sync_routers(app)
        await self.sync_services(app)

    def sync_routers(self, app: "FastAPI") -> None:
        """Смонтировать роутеры новых установленных, вырезать роутеры
        удалённых. Идемпотентно."""
        env: "Environment" = app.state.env
        for code in env.apps.get_names():
            if code in env.installed and code not in env._routes:
                env._mount(app, code)
            elif code not in env.installed and code in env._routes:
                env._unmount(app, code)

    async def sync_services(self, app: "FastAPI") -> None:
        """Отключаемые сервисы: установленный — startup, удалённый —
        shutdown. Идемпотентно."""
        env: "Environment" = app.state.env
        for code in env.services_before + env.services_after:
            if is_core(env.apps, code):
                continue
            if code in env.installed and code not in env.running:
                await env.start_service(app, code)
            elif code not in env.installed and code in env.running:
                await env.stop_service(app, code)
