# Copyright 2025 FARA CRM
# Duplicates module — правила дубликатов, навешанные на Partner и Contact

"""
Каждое правило — одна функция под @constrains (dotorm): режим из системных
настроек, один пакетный search по всем записям операции, при block —
FaraException 400 с кодом DUPLICATE_* и найденной записью в detail (общая
модалка ошибок на фронте, как USER_LOGIN_EXISTS), при warn — совпадение
в лог, запись проходит.

Правило получает все записи операции сразу (одну у create/update, все
строки у bulk) и ходит в базу одним IN-запросом, а не по запросу на строку.
Дубли внутри самой пачки (две новых записи с одним значением) в базе ещё
не видны — ловятся в том же цикле. На update payload несёт только
изменённые поля: правило, которому нужны остальные, после проверки режима
читает их одним search по id записей — ни одного запроса, если правило
выключено.

Правила работают только у установленного приложения duplicates: @extend
навешивается при импорте, поэтому флаг проверяется в _mode — снял
приложение на странице приложений, правила молчат. Ключи режимов сеет
DuplicatesApp.post_init с cache_ttl=-1: читаются из памяти, смена значения
требует рестарта. Значение warn / block, пусто — выключено; по умолчанию
block только у контакта партнёра.
"""

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from backend.base.crm.partners.models.contact import Contact
from backend.base.crm.partners.models.partners import Partner
from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.core.extensions import extend
from backend.base.system.dotorm.dotorm.decorators import constrains
from backend.base.system.dotorm.dotorm.model import DotModel

# поддержка IDE, видны все атрибуты базового класса; у партнёра ещё и
# реквизиты (vat/kpp) из contract
if TYPE_CHECKING:
    from backend.base.crm.contract.models.requisites_ext import RequisitesMixin

    class _PartnerBase(RequisitesMixin, Partner): ...

    _ContactBase = Contact
else:
    _PartnerBase = object
    _ContactBase = object

log = logging.getLogger(__name__)

APP_CODE = "duplicates"


class DuplicateMode(StrEnum):
    """Режим правила: warn — совпадение в лог, block — 400. Пусто — выключено."""

    WARN = "warn"
    BLOCK = "block"


async def _mode(key: str) -> DuplicateMode | None:
    """Режим правила из системных настроек (кеш навсегда, без запроса);
    приложение не установлено, пусто или неизвестное значение — выключено."""
    if not env.is_installed(APP_CODE):
        return None
    value = await env.models.system_settings.sudo().get_value(key)
    return DuplicateMode(value) if value in DuplicateMode else None


def _report(mode: DuplicateMode, code: str, found: str) -> None:
    """Найден дубль: block — отклонить операцию, warn — записать в лог."""
    if mode == DuplicateMode.BLOCK:
        raise FaraException(
            {"content": code, "detail": found, "status_code": 400}
        )
    log.warning("%s: %s", code, found)


def _owner_id(value):
    """id из значения M2O: инстанс модели (из payload) или голый int (из БД)."""
    return getattr(value, "id", value)


async def _read_missing(
    model: DotModel, records: list[DotModel], fields: list[str]
) -> None:
    """На update дочитать в незаданные поля записей их хранимые значения —
    одним search по всем id пачки; значения клиента остаются в приоритете."""
    ids = [record.id for record in records if record.id]
    if not ids:
        return
    stored = {
        row.id: row
        for row in await model.sudo().search(
            filter=[("id", "in", ids)], fields=fields
        )
    }
    for record in records:
        row = stored.get(record.id)
        if row is None:
            continue
        for name in fields:
            if not record.is_assigned(name):
                setattr(record, name, getattr(row, name))


@extend(Partner)
class PartnerDuplicatesMixin(_PartnerBase):
    """
    Партнёр: имя (без учёта регистра) и пара ИНН + КПП (поле vat даёт
    contract; филиалы одного юрлица различаются КПП — один ИНН не дубль).
    Архивные партнёры не считаются. block по имени действует и на
    автосоздание партнёра из входящих (Contact.create_with_partner) —
    поэтому по умолчанию правило имени выключено.
    """

    DUPLICATE_NAME_KEY = "constrains.partners.duplicate_name"
    DUPLICATE_VAT_KEY = "constrains.partners.duplicate_vat_kpp"

    @constrains("name")
    async def _constrains_duplicate_name(self, records: list[Self]) -> None:
        mode = await _mode(self.DUPLICATE_NAME_KEY)
        if mode is None:
            return
        by_name = {}
        for record in records:
            if not record.name:
                continue
            key = record.name.strip().lower()
            if key in by_name:  # дубль внутри пачки
                _report(mode, "DUPLICATE_NAME", record.name)
            by_name[key] = record
        if not by_name:
            return
        # Регистронезависимо: ilike без масок — равенство; в пачке — OR.
        names = []
        for record in by_name.values():
            if names:
                names.append("or")
            names.append(("name", "ilike", record.name.strip()))
        found = await self.sudo().search(
            filter=[("active", "=", True), names], fields=["id", "name"]
        )
        for other in found:
            record = by_name.get(other.name.strip().lower())
            if record is not None and other.id != record.id:
                _report(mode, "DUPLICATE_NAME", other.name)

    @constrains("vat", "kpp")
    async def _constrains_duplicate_vat(self, records: list[Self]) -> None:
        mode = await _mode(self.DUPLICATE_VAT_KEY)
        if mode is None:
            return
        await _read_missing(self, records, ["vat", "kpp"])
        by_key = {}
        for record in records:
            if not record.vat:
                continue
            key = (record.vat, record.kpp or None)
            if key in by_key:  # дубль внутри пачки
                _report(mode, "DUPLICATE_VAT", record.vat)
            by_key[key] = record
        if not by_key:
            return
        found = await self.sudo().search(
            filter=[
                ("vat", "in", [vat for vat, _ in by_key]),
                ("active", "=", True),
            ],
            fields=["id", "name", "vat", "kpp"],
        )
        for other in found:
            record = by_key.get((other.vat, other.kpp or None))
            if record is not None and other.id != record.id:
                _report(mode, "DUPLICATE_VAT", other.name)


@extend(Contact)
class ContactDuplicatesMixin(_ContactBase):
    """
    Контакт: тот же value у активного контакта другого владельца.
    Партнёрские (partner_id) и операторские (user_id) контакты — отдельные
    ключи режима. value уже канонический (Contact.create / update).
    """

    DUPLICATE_KEYS = {
        "partner_id": "constrains.contacts.duplicate_value",
        "user_id": "constrains.contacts.duplicate_value_operators",
    }
    DUPLICATE_CODES = {
        "partner_id": "DUPLICATE_CONTACT",
        "user_id": "DUPLICATE_CONTACT_OPERATOR",
    }

    @constrains("value", "contact_type_id", "partner_id", "user_id")
    async def _constrains_duplicate_value(self, records: list[Self]) -> None:
        # Область (партнёр / сотрудник) известна только по владельцу, а он на
        # update может быть не в payload — поэтому сначала оба режима из
        # кеша, и лишь если хоть один включён, дочитываем записи.
        modes = {
            field: await _mode(key)
            for field, key in self.DUPLICATE_KEYS.items()
        }
        if not any(modes.values()):
            return
        await _read_missing(self, records, ["value", "partner_id", "user_id"])
        for owner_field, mode in modes.items():
            if mode is None:
                continue
            code = self.DUPLICATE_CODES[owner_field]
            # value → владелец среди записей этой области
            owners = {}
            for record in records:
                scope = "user_id" if record.user_id else "partner_id"
                if scope != owner_field or not record.value:
                    continue
                owner_id = _owner_id(getattr(record, owner_field))
                if owners.get(record.value, owner_id) != owner_id:
                    _report(mode, code, record.value)  # дубль внутри пачки
                owners[record.value] = owner_id
            if not owners:
                continue
            found = await self.sudo().search(
                filter=[
                    ("value", "in", list(owners)),
                    ("active", "=", True),
                    (owner_field, "!=", None),
                ],
                fields=["id", "value", owner_field],
                fields_nested={owner_field: {"fields": ["id", "name"]}},
            )
            for other in found:
                other_owner = getattr(other, owner_field)
                if other_owner.id != owners[other.value]:
                    _report(mode, code, other_owner.name)
