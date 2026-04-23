from pydantic_settings import BaseSettings


class SettingsCore(BaseSettings):
    """Config configurations."""

    site_url: str = "http://127.0.0.1:5173"
    api_url: str = "http://127.0.0.1:8090"
