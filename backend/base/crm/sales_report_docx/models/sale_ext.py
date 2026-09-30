# Copyright 2025 FARA CRM
# Sales Report DOCX module — Sale model extension: report data functions

"""
Функции данных печатных форм и отчётов по продажам (report_docx).

Функция данных — @staticmethod `(env, **params) -> dict`, ключи дикта =
теги DOCX-шаблона. В записи шаблона (report_template): model_name = sales
(имя таблицы, как в /auto/{model}), python_function = имя функции. Два вида:

- документ по записи (report_type = record): params = {"record_id": id},
  приходит с кнопки «Печать» на форме заказа — `sale_invoice_rus`;
- сводный отчёт (report_type = summary): params — что угодно (период,
  сотрудник…), приходят из kwargs cron-задачи или ?params= роута —
  `sales_period_data`.

Свою функцию добавляют так же: @extend(Sale) в своём модуле (или в
backend/business), любые запросы, любые ключи, DOCX с тегами по этим ключам.
Документы по договору (образцы договоров) — contract_ext.py, contract_data.

Теги шаблона «Счёт на оплату 2018.docx» (sale_invoice_rus):
  {{bank_received}}, {{bik}}, {{acc_number}}, {{inn}}, {{kpp}},
  {{correspondent_account}}, {{reciver}}, {{so_number}}, {{so_from}},
  {{provider}}, {{customer}}, {{contract}}, {{manager}},
  {{order_line}} (loop: index, name, qty, product_uom, price, total_price),
  {{summ}}, {{summ_nds}}, {{len_order_line}}, {{summ_text}},
  {{chief}}, {{accountant}}

Теги шаблона «Отчёт по продажам за период.docx» (sales_period_data):
  {{date_from}}, {{date_to}}, {{count}}, {{total}},
  {{rows}} (loop: name, date, partner, user, stage, amount),
  {{by_user}} (loop: user, count, amount)
"""

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.report_docx.utils.fields import (
    ReportField,
    ReportList,
    report_fields,
)
from backend.base.crm.sales.models.sale import Sale

if TYPE_CHECKING:
    _Base = Sale
    from backend.base.system.core.enviroment import Environment
else:
    _Base = object


# ─── helpers ────────────────────────────────────────────────


def _numer(name: str | None) -> str:
    """Извлечь число из конца строки: 'SO042' → '042'"""
    if name:
        m = re.findall(r"\d+$", name)
        if m:
            return m[0]
    return ""


def _initials(fio: str | None) -> str:
    """'Иванов Иван Иванович' → 'Иванов И.И.'"""
    if not fio:
        return ""
    parts = fio.strip().split()
    if len(parts) == 1:
        return parts[0]
    return parts[0] + " " + "".join(p[0] + "." for p in parts[1:])


def _format_money(amount: float) -> str:
    """12345.60 → '12 345,60'"""
    int_part = int(amount)
    dec_part = round((amount - int_part) * 100)
    int_str = f"{int_part:,}".replace(",", " ")
    return f"{int_str},{dec_part:02d}"


def _rubles_text(amount: float) -> str:
    """Сумма прописью. pytils если есть, иначе fallback."""
    try:
        from pytils import numeral

        text_rubles = numeral.rubles(int(amount))
        copeck = round((amount - int(amount)) * 100)
        text_copeck = numeral.choose_plural(
            int(copeck), ("копейка", "копейки", "копеек")
        )
        return f"{text_rubles} {copeck:02d} {text_copeck}"
    except ImportError:
        return f"{_format_money(amount)} руб."


def _ru_date(date_str: str | None) -> str:
    """Дата на русском: '02 февраля 2026 г.'"""
    if not date_str or date_str == "False":
        return ""
    try:
        from pytils import dt as pytils_dt

        if "T" in str(date_str) or " " in str(date_str):
            d = datetime.fromisoformat(str(date_str).replace("Z", ""))
        else:
            d = datetime.strptime(str(date_str), "%Y-%m-%d")
        return pytils_dt.ru_strftime("%d %B %Y г.", date=d, inflected=True)
    except (ImportError, ValueError):
        return str(date_str)[:10] if date_str else ""


def _rel_id(value) -> int | None:
    """id связи: снаружи ORM отдаёт Many2one записью, а внутри вложенных
    записей (строки заказа, компания внутри заказа) — числом."""
    if value is None:
        return None
    return value.id if isinstance(value, DotModel) else int(value)


async def _by_id(model_cls, records, field_names, fields) -> dict:
    """Догрузить связанные записи пачкой: {id: запись} по значениям
    полей field_names у records (числа или записи)."""
    ids = {
        _rel_id(getattr(record, name))
        for record in records
        for name in field_names
    } - {None}
    if not ids:
        return {}
    found = await model_cls.search(
        filter=[("id", "in", list(ids))], fields=list(fields)
    )
    return {record.id: record for record in found}


# ─── extension ──────────────────────────────────────────────


@extend(Sale)
class SaleReportMixin(_Base):
    """Расширение Sale: функции данных для DOCX-шаблонов."""

    # ------------------------------------------------------------------
    # Документ по записи
    # ------------------------------------------------------------------

    @staticmethod
    @report_fields(
        # Ключи дикта ниже — для каталога конструктора (поля функции)
        bank_received="Банк получателя",
        bik="БИК",
        acc_number="Расчётный счёт",
        inn="ИНН поставщика",
        kpp="КПП поставщика",
        correspondent_account="Корр. счёт",
        reciver="Получатель",
        so_number="Номер счёта",
        so_from="Дата счёта",
        provider="Поставщик",
        customer="Покупатель",
        contract="Основание",
        manager="Менеджер",
        order_line=ReportList(
            "Позиции счёта",
            index="№",
            name="Наименование",
            qty="Кол-во",
            product_uom="Ед.",
            price=ReportField("Цена", "money"),
            total_price=ReportField("Сумма", "money"),
        ),
        len_order_line="Кол-во позиций",
        summ=ReportField("Итого", "money"),
        summ_nds=ReportField("В т.ч. НДС", "money"),
        summ_text="Сумма прописью",
        chief="Руководитель",
        accountant="Бухгалтер",
    )
    async def sale_invoice_rus(env: "Environment", record_id: int) -> dict:
        """
        Подготовка данных для «Счёт на оплату 2018.docx» (sale).
        Имена переменных точно совпадают с тегами в шаблоне.
        """
        sale = await env.models.sale.search_one(
            filter=[("id", "=", record_id)],
            fields=[
                "id",
                "name",
                "date_order",
                "notes",
                "partner_id",
                "user_id",
                "company_id",
                "order_line_ids",
            ],
            fields_nested={
                "partner_id": {"fields": ["id", "name", "vat", "kpp"]},
                "user_id": {"fields": ["id", "name"]},
                "company_id": {
                    "fields": [
                        "id",
                        "name",
                        "vat",
                        "kpp",
                        "bank_name",
                        "bank_bic",
                        "bank_account",
                        "bank_corr_account",
                        "chief_id",
                        "accountant_id",
                    ]
                },
                "order_line_ids": {
                    "fields": [
                        "id",
                        "sequence",
                        "product_uom_qty",
                        "price_unit",
                        "price_subtotal",
                        "price_tax",
                        "price_total",
                        "notes",
                        "product_id",
                        "product_uom_id",
                        "tax_id",
                    ]
                },
            },
        )

        if not sale:
            raise ValueError(f"Sale order #{record_id} not found")

        # ── Компания ──
        company = sale.company_id
        company_name = company.name or "" if company else ""
        company_inn = company.vat or "" if company else ""
        company_kpp = company.kpp or "" if company else ""

        # Руководитель и бухгалтер — связи внутри вложенной компании
        # приходят числами, догружаем имена одним запросом
        signers = await _by_id(
            env.models.user,
            [company] if company else [],
            ("chief_id", "accountant_id"),
            ["id", "name"],
        )
        chief = signers.get(_rel_id(company.chief_id)) if company else None
        chief_name = _initials(chief.name) if chief and chief.name else ""

        accountant = (
            signers.get(_rel_id(company.accountant_id)) if company else None
        )
        accountant_name = (
            _initials(accountant.name)
            if accountant and accountant.name
            else ""
        )

        # ── Покупатель ──
        partner = sale.partner_id
        partner_name = partner.name or "" if partner else ""
        # ИНН — поле vat из RequisitesMixin (у компании такое же)
        partner_inn = partner.vat or "" if partner else ""
        partner_kpp = partner.kpp or "" if partner else ""

        # ── Менеджер ──
        user = sale.user_id
        manager_name = user.name or "" if user else ""

        # ── Представления (provider / customer) ──
        provider_parts = [company_name]
        if company_inn:
            provider_parts.append(f"ИНН {company_inn}")
        if company_kpp:
            provider_parts.append(f"КПП {company_kpp}")
        provider = ", ".join(p for p in provider_parts if p)

        customer_parts = [partner_name]
        if partner_inn:
            customer_parts.append(f"ИНН {partner_inn}")
        if partner_kpp:
            customer_parts.append(f"КПП {partner_kpp}")
        customer = ", ".join(p for p in customer_parts if p)

        # ── Номер и дата ──
        now = datetime.now()
        sale_name = sale.name or ""
        so_number = _numer(sale_name) + "-" + str(now.month) + str(now.day)
        so_from = _ru_date(now.strftime("%Y-%m-%d %H:%M:%S"))

        # ── Строки заказа ──
        order_line = []
        summ = 0.0
        summ_nds = 0.0

        raw_lines = sale.order_line_ids or []
        # Внутри строк заказа товар, единица и налог — числа (вложенность
        # ORM один уровень): догружаем их пачкой, по запросу на модель
        products = await _by_id(
            env.models.product, raw_lines, ("product_id",), ["id", "name"]
        )
        uoms = await _by_id(
            env.models.uom, raw_lines, ("product_uom_id",), ["id", "name"]
        )
        taxes = await _by_id(
            env.models.tax, raw_lines, ("tax_id",), ["id", "amount"]
        )
        for line in raw_lines:
            qty = float(line.product_uom_qty or 0)
            price = float(line.price_unit or 0)

            if qty <= 0:
                continue

            # Расчёт НДС
            nds_rate = 0.0
            tax = taxes.get(_rel_id(line.tax_id))
            if tax and tax.amount:
                tax_amount = float(tax.amount)
                nds_rate = tax_amount / (100 + tax_amount)

            total_price = price * qty
            line_nds = total_price * nds_rate

            product = products.get(_rel_id(line.product_id))
            product_name = (product.name or "") if product else ""
            uom = uoms.get(_rel_id(line.product_uom_id))
            uom_name = (uom.name or "") if uom else ""

            order_line.append(
                {
                    "index": len(order_line) + 1,
                    "name": product_name or line.notes or "",
                    "qty": qty,
                    "product_uom": uom_name or "шт.",
                    "currency": "руб.",
                    "price": price,
                    "total_price": round(total_price, 2),
                }
            )

            summ += total_price
            summ_nds += line_nds

        return {
            # Банковские реквизиты компании (RequisitesMixin)
            "bank_received": company.bank_name or "" if company else "",
            "bik": company.bank_bic or "" if company else "",
            "acc_number": company.bank_account or "" if company else "",
            "inn": company_inn,
            "kpp": company_kpp,
            "correspondent_account": (
                company.bank_corr_account or "" if company else ""
            ),
            # Получатель
            "reciver": company_name,
            # Номер и дата
            "so_number": so_number,
            "so_from": so_from,
            # Стороны
            "provider": provider,
            "customer": customer,
            # Основание (TODO: связь с contract)
            "contract": "",
            # Менеджер
            "manager": f"Менеджер: {manager_name}" if manager_name else "",
            # Строки заказа
            "order_line": order_line,
            "len_order_line": len(order_line),
            # Итого
            "summ": round(summ, 2),
            "summ_nds": round(summ_nds, 2),
            "summ_text": _rubles_text(summ).capitalize(),
            # Подписи
            "chief": chief_name,
            "accountant": accountant_name,
            # Изображения (печати/подписи — пустые по умолчанию)
            "images": [False, False, False],
        }

    # ------------------------------------------------------------------
    # Сводный отчёт — дикт собирается кодом, а не берётся из одной записи
    # ------------------------------------------------------------------

    @staticmethod
    @report_fields(
        date_from="Начало периода",
        date_to="Конец периода",
        count="Сделок",
        total="Сумма за период",
        rows=ReportList(
            "Сделки",
            name="Заказ",
            date="Дата",
            partner="Клиент",
            user="Менеджер",
            stage="Стадия",
            amount="Сумма",
        ),
        by_user=ReportList(
            "Итоги по менеджерам",
            user="Менеджер",
            count="Сделок",
            amount="Сумма",
        ),
    )
    async def sales_period_data(env: "Environment", days: int = 30) -> dict:
        """Продажи за последние N дней: список сделок и итоги по менеджерам.
        Шаблон — «Отчёт по продажам за период.docx»."""
        date_to = datetime.now(timezone.utc)
        date_from = date_to - timedelta(days=days)
        sales = await env.models.sale.search(
            filter=[("active", "=", True), ("date_order", ">=", date_from)],
            fields=[
                "id",
                "name",
                "date_order",
                "amount_total",
                "partner_id",
                "user_id",
                "stage_id",
            ],
            fields_nested={
                "partner_id": {"fields": ["id", "name"]},
                "user_id": {"fields": ["id", "name"]},
                "stage_id": {"fields": ["id", "name"]},
            },
            sort="date_order",
            order="ASC",
        )

        rows = []
        by_user: dict[str, dict] = {}
        for sale in sales:
            user = sale.user_id.name if sale.user_id else "—"
            amount = float(sale.amount_total or 0)
            rows.append(
                {
                    "name": sale.name,
                    "date": (
                        sale.date_order.strftime("%d.%m.%Y")
                        if sale.date_order
                        else ""
                    ),
                    "partner": sale.partner_id.name if sale.partner_id else "",
                    "user": user,
                    "stage": sale.stage_id.name if sale.stage_id else "",
                    "amount": _format_money(amount),
                }
            )
            totals = by_user.setdefault(
                user, {"user": user, "count": 0, "amount": 0.0}
            )
            totals["count"] += 1
            totals["amount"] += amount

        return {
            "date_from": date_from.strftime("%d.%m.%Y"),
            "date_to": date_to.strftime("%d.%m.%Y"),
            "count": len(rows),
            "total": _format_money(sum(t["amount"] for t in by_user.values())),
            "rows": rows,
            "by_user": [
                {**t, "amount": _format_money(t["amount"])}
                for t in sorted(by_user.values(), key=lambda t: -t["amount"])
            ],
        }
