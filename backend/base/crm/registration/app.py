# Copyright 2025 FARA CRM
# Registration module - самостоятельная регистрация с подтверждением кодом

from backend.base.system.core.app import App


class RegistrationApp(App):
    """
    Регистрация пользователя по коду подтверждения.

    Модуль не знает, как доставить код: каналы (email, telegram, …)
    подключаются отдельными модулями через register_channel. Кого создавать
    (роль, «Рабочее место», стартовая страница) — настройка
    registration.new_user, её задаёт модуль-потребитель (маркетплейс).
    """

    info = {
        "name": "Registration",
        "summary": "Self-registration with confirmation code",
        "author": "FARA CRM",
        "category": "Base",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["users", "security"],
        # Публичная регистрация включается осознанно (сама или как
        # зависимость маркетплейса), а не при первом старте.
        "auto_install": False,
    }
