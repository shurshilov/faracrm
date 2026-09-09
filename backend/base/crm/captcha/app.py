# Copyright 2025 FARA CRM
# Captcha module - application

from backend.base.system.core.app import App


class CaptchaApp(App):
    """
    Простая капча «a + b» для публичных форм — независимый инструмент.

    Задачка живёт строкой в БД, ответ проверяется на сервере и гасится.
    Модуль ни о ком не знает: даёт публичную ручку GET /captcha/new и
    проверку CaptchaChallenge.verify(token, answer). Кому нужна защита от
    ботов — тот зависит от captcha и вызывает проверку сам (см. registration).
    """

    info = {
        "name": "Captcha",
        "summary": "Simple math captcha for public forms",
        "author": "FARA CRM",
        "category": "Base",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        # Ставится как зависимость того, кто её использует (например,
        # registration)
        "auto_install": False,
    }
