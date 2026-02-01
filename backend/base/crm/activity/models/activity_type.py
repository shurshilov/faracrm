from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Boolean,
)
from backend.base.system.dotorm.dotorm.model import DotModel


class ActivityType(DotModel):
    """
    Тип активности.

    Примеры: Звонок, Встреча, Email, Напоминание, Todo.
    Определяет иконку, цвет, дефолтное количество дней до дедлайна.
    """

    __table__ = "activity_type"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=255, required=True, description="Название типа")
    icon: str | None = Char(max_length=100, description="Имя иконки (tabler icon)")
    color: str = Char(max_length=20, default="#228be6", description="Цвет")
    default_days: int = Integer(default=1, description="Дней до дедлайна по умолчанию")
    sequence: int = Integer(default=10, description="Порядок сортировки")
    active: bool = Boolean(default=True)


INITIAL_ACTIVITY_TYPES = [
    {
        "name": "Звонок",
        "icon": "IconPhone",
        "color": "#22b8cf",
        "default_days": 0,
        "sequence": 1,
    },
    {
        "name": "Встреча",
        "icon": "IconCalendarEvent",
        "color": "#7950f2",
        "default_days": 1,
        "sequence": 2,
    },
    {
        "name": "Email",
        "icon": "IconMail",
        "color": "#fab005",
        "default_days": 1,
        "sequence": 3,
    },
    {
        "name": "Напоминание",
        "icon": "IconBell",
        "color": "#fd7e14",
        "default_days": 3,
        "sequence": 4,
    },
    {
        "name": "Задача",
        "icon": "IconCheckbox",
        "color": "#40c057",
        "default_days": 7,
        "sequence": 5,
    },
]
