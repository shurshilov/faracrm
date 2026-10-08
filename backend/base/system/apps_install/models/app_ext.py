"""
Флаг «установлено» у строки реестра приложений (модуль apps, apps/models/apps.py).

Без модуля apps_install флага нет вовсе: активно всё, что перечислено в
project_setup. С модулем это единственное состояние приложения в БД; всё
остальное (описание, версия, зависимости) живёт в info и отдаётся
каталогом из памяти.
"""

from backend.base.system.core.extensions import extend
from backend.base.system.apps.models.apps import App
from backend.base.system.dotorm.dotorm.fields import Boolean


@extend(App)
class AppInstalled:
    # Флаг решает, отвечают ли роуты приложения, стартует ли его
    # отключаемый сервис, видно ли оно в меню и работают ли его
    # cron-задачи. DEFAULT в БД — чтобы у строк, существовавших до
    # появления колонки, ничего не изменилось.
    installed: bool = Boolean(
        default=True,
        default_db=True,
        description="Установлено (роуты, меню, CRUD, cron)",
    )
