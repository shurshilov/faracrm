# Copyright 2025 FARA CRM
# Contract module — провайдер реквизитов: источник данных по ИНН и БИК

import logging

from backend.base.system.core.enviroment import env

logger = logging.getLogger(__name__)


class RequisitesProviderBase:
    """
    Источник реквизитов контрагента по ИНН и банка по БИК — отдельный модуль
    на каждого (dadata, …). Сам contract знает только этот интерфейс:
    кнопка «Заполнить» у поля зовёт /requisites/party и /requisites/bank
    (routers/requisites.py), те спрашивают провайдера и отдают форме то,
    что он вернул.

    Оба метода возвращают словарь «поле Partner → значение», готовый к
    подстановке в форму, или пустой словарь, если ничего не найдено.
    Ошибки настройки/связи провайдер поднимает FaraException — фронт
    покажет их пользователю.
    """

    # Код приложения-модуля (имя в Apps): провайдер действует, пока
    # приложение установлено. Регистрируется он при импорте, а установка
    # решается в БД — иначе удалённый из интерфейса модуль продолжал бы
    # ходить в API.
    app_code: str = ""

    async def party_by_inn(self, inn: str) -> dict:
        """Юрлицо/ИП по ИНН → {name, partner_type, kpp, ogrn, okpo, address}."""
        raise NotImplementedError

    async def bank_by_bic(self, bic: str) -> dict:
        """Банк по БИК → {bank_name, bank_corr_account}."""
        raise NotImplementedError


_provider: RequisitesProviderBase | None = None


def register_provider(provider_class: type[RequisitesProviderBase]) -> None:
    """Зарегистрировать провайдера (вызывается из __init__ его модуля)."""
    global _provider
    _provider = provider_class()
    logger.info("Registered requisites provider: %s", _provider.app_code)


def get_provider() -> RequisitesProviderBase | None:
    """Действующий провайдер или None, если модуль не подключён/не установлен."""
    if _provider is None or not env.is_installed(_provider.app_code):
        return None
    return _provider
