from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Boolean,
    Integer,
)
from backend.base.system.dotorm.dotorm.model import DotModel


class Language(DotModel):
    """Модель языка системы"""
    __table__ = "language"

    id: int = Integer(primary_key=True)
    code: str = Char(max_length=5)    # 'en', 'ru', 'de', 'fr', 'it'
    name: str = Char()                 # 'English', 'Русский'
    flag: str = Char(max_length=10)    # 'us', 'ru', 'de', 'fr', 'it'
    active: bool = Boolean(default=False)  # Доступен ли в селекторе


# Начальные данные для языков
INITIAL_LANGUAGES = [
    {"code": "en", "name": "English", "flag": "us", "active": True},
    {"code": "ru", "name": "Русский", "flag": "ru", "active": True},
    {"code": "de", "name": "Deutsch", "flag": "de", "active": False},
    {"code": "fr", "name": "Français", "flag": "fr", "active": False},
    {"code": "it", "name": "Italiano", "flag": "it", "active": False},
]
