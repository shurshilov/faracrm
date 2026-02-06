from backend.base.system.dotorm.dotorm.fields import Boolean, Char, Integer
from backend.base.system.dotorm.dotorm.model import DotModel


class App(DotModel):
    """
    Приложение/модуль системы.

    Используется для:
    - Группировки ролей по приложениям в UI
    - Отслеживания установленных модулей
    """

    __table__ = "apps"

    id: int = Integer(primary_key=True)
    code: str = Char(max_length=64, unique=True)
    name: str = Char(max_length=128)
    active: bool = Boolean(default=True)
    sequence: int = Integer(default=10, description="Порядок в очереди")
