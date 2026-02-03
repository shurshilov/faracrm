# Copyright 2025 FARA CRM
# Contract module — Sale model extension for report data functions

"""
Данные для шаблона «Счёт на оплату 2018.docx».

Теги шаблона:
  {{bank_received}}, {{bik}}, {{acc_number}}, {{inn}}, {{kpp}},
  {{correspondent_account}}, {{reciver}}, {{so_number}}, {{so_from}},
  {{provider}}, {{customer}}, {{contract}}, {{manager}},
  {{order_line}} (loop: index, name, qty, product_uom, price, total_price),
  {{summ}}, {{summ_nds}}, {{len_order_line}}, {{summ_text}},
  {{chief}}, {{accountant}}
"""

import re
from datetime import datetime
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
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


# ─── extension ──────────────────────────────────────────────


@extend(Sale)
class SaleContractMixin(_Base):
    """
    Расширение Sale для модуля contract.
    Добавляет методы подготовки данных для отчётов.
    """

    @staticmethod
    async def sale_invoice_rus(env: "Environment", record_id: int) -> dict:
        """
        Подготовка данных для «Счёт на оплату 2018.docx» (sale).
        Имена переменных точно совпадают с тегами в шаблоне.
        """
        records = await env.models.sale.search(
            filter=[("id", "=", record_id)],
            limit=1,
            fields=[
                "id",
                "name",
                "date_order",
                "notes",
                "parent_id",
                "user_id",
                "company_id",
                "order_line_ids",
            ],
            fields_nested={
                "parent_id": ["id", "name", "vat", "inn", "kpp"],
                "user_id": ["id", "name"],
                "company_id": [
                    "id",
                    "name",
                    "inn",
                    "kpp",
                    "chief_id",
                    "accountant_id",
                ],
                "company_id.chief_id": ["id", "name"],
                "company_id.accountant_id": ["id", "name"],
                "order_line_ids": [
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
                ],
                # "order_line_ids.product_id": ["id", "name"],
                # "order_line_ids.product_uom_id": ["id", "name"],
                # "order_line_ids.tax_id": ["id", "amount"],
            },
        )

        if not records:
            raise ValueError(f"Sale order #{record_id} not found")

        sale = records[0]

        # ── Компания ──
        company = sale.company_id
        company_name = company.name or "" if company else ""
        company_inn = company.inn or "" if company else ""
        company_kpp = company.kpp or "" if company else ""

        # Руководитель и бухгалтер
        chief = company.chief_id if company else None
        chief_name = _initials(chief.name) if chief and chief.name else ""

        accountant = company.accountant_id if company else None
        accountant_name = (
            _initials(accountant.name)
            if accountant and accountant.name
            else ""
        )

        # ── Покупатель ──
        partner = sale.parent_id
        partner_name = partner.name or "" if partner else ""
        partner_inn = partner.inn or "" if partner else ""
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
        for line in raw_lines:
            qty = float(line.product_uom_qty or 0)
            price = float(line.price_unit or 0)

            if qty <= 0:
                continue

            # Расчёт НДС
            nds_rate = 0.0
            tax = line.tax_id
            if tax and tax.amount:
                tax_amount = float(tax.amount)
                nds_rate = tax_amount / (100 + tax_amount)

            total_price = price * qty
            line_nds = total_price * nds_rate

            product_name = (
                line.product_id.name or "" if line.product_id else ""
            )
            uom_name = (
                line.product_uom_id.name or "" if line.product_uom_id else ""
            )

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
            # Банковские реквизиты (TODO: добавить bank_ids в Company)
            "bank_received": "",
            "bik": "",
            "acc_number": "",
            "inn": company_inn,
            "kpp": company_kpp,
            "correspondent_account": "",
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
