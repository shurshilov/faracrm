from pydantic_settings import BaseSettings


class SettingsCore(BaseSettings):
    """Config configurations."""

    # Базовый URL сервера для генерации webhook URL и других внешних ссылок
    # Может быть задан через переменную окружения BASE_URL
    # Пример: https://api.example.com
    base_url: str = "http://localhost:8090"
