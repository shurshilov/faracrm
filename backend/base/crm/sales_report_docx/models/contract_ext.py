# Copyright 2025 FARA CRM
# Sales Report DOCX module — Contract model extension: report data function

"""
Функция данных печатных форм договора (report_docx): `contract_data` — один
дикт для всех образцов договоров из templates/ (договор с клиентом и с
поставщиком, договор-счёт, дополнительное соглашение, уведомление об
уполномоченных лицах). Теги образцов исторические: c_* — своя компания,
partner_* и p_* — контрагент и его банк, contract_* — договор, order_line —
строки заказов по договору; ключи здесь именно такие, свои теги добавляют в
конструкторе. Чего в моделях нет — руководитель контрагента (customer_dir,
p_print_dir), телефоны и e-mail компании (c_phone, c_mobile, c_email) — уходит
пустым.
"""

from datetime import date
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.contract.models.contract import Contract
from backend.base.crm.report_docx.utils.fields import ReportList, report_fields
from .sale_ext import _by_id, _format_money, _initials, _rel_id, _ru_date

if TYPE_CHECKING:
    _Base = Contract
    from backend.base.system.core.enviroment import Environment
else:
    _Base = object

# Реквизиты стороны (RequisitesMixin: одинаковы у Partner и Company)
REQUISITE_FIELDS = [
    "id",
    "name",
    "vat",
    "kpp",
    "ogrn",
    "okpo",
    "address",
    "bank_name",
    "bank_bic",
    "bank_account",
    "bank_corr_account",
]


def _party(record, prefix: str, bank_prefix: str) -> dict:
    """Реквизиты стороны под тегами образцов: {prefix}name/inn/kpp/ogrn/okpo/
    address и {bank_prefix}bank_name/bank_bic/acc_number/cor_number."""

    def get(name: str) -> str:
        return (getattr(record, name, None) or "") if record else ""

    return {
        f"{prefix}name": get("name"),
        f"{prefix}inn": get("vat"),
        f"{prefix}kpp": get("kpp"),
        f"{prefix}ogrn": get("ogrn"),
        f"{prefix}okpo": get("okpo"),
        f"{prefix}address": get("address"),
        f"{bank_prefix}bank_name": get("bank_name"),
        f"{bank_prefix}bank_bic": get("bank_bic"),
        f"{bank_prefix}acc_number": get("bank_account"),
        f"{bank_prefix}cor_number": get("bank_corr_account"),
    }


async def _partner_contacts(
    env: "Environment", partner_id: int | None
) -> dict:
    """Телефоны и e-mail контрагента из его контактов: первый телефон —
    p_phone, второй — p_mobile, первый e-mail — p_email; основной контакт
    (is_primary) идёт первым."""
    result = {"p_phone": "", "p_mobile": "", "p_email": ""}
    if not partner_id:
        return result
    contacts = await env.models.contact.search(
        filter=[("partner_id", "=", partner_id), ("active", "=", True)],
        fields=["id", "value", "name", "contact_type_id", "is_primary"],
    )
    types = await _by_id(
        env.models.contact_type, contacts, ("contact_type_id",), ["id", "name"]
    )
    phones: list[str] = []
    for contact in sorted(contacts, key=lambda c: not c.is_primary):
        contact_type = types.get(_rel_id(contact.contact_type_id))
        code = contact_type.name if contact_type else ""
        value = contact.value or contact.name or ""
        if code == "phone" and value:
            phones.append(value)
        elif code == "email" and value and not result["p_email"]:
            result["p_email"] = value
    result["p_phone"] = phones[0] if phones else ""
    result["p_mobile"] = phones[1] if len(phones) > 1 else ""
    return result


@extend(Contract)
class ContractReportMixin(_Base):
    """Расширение Contract: функция данных для DOCX-образцов договоров."""

    @staticmethod
    @report_fields(
        c_name="Компания",
        c_inn="ИНН компании",
        c_kpp="КПП компании",
        c_ogrn="ОГРН компании",
        c_okpo="ОКПО компании",
        c_address="Адрес компании",
        c_bank_name="Банк компании",
        c_bank_bic="БИК компании",
        c_acc_number="Р/с компании",
        c_cor_number="К/с компании",
        c_phone="Телефон компании",
        c_mobile="Мобильный компании",
        c_email="E-mail компании",
        our_dir="Руководитель компании",
        c_print_dir="Руководитель компании (инициалы)",
        contract_company_name="Компания в договоре",
        partner_name="Контрагент",
        partner_inn="ИНН контрагента",
        partner_kpp="КПП контрагента",
        partner_ogrn="ОГРН контрагента",
        partner_okpo="ОКПО контрагента",
        partner_address="Адрес контрагента",
        p_bank_name="Банк контрагента",
        p_bank_bic="БИК контрагента",
        p_acc_number="Р/с контрагента",
        p_cor_number="К/с контрагента",
        p_phone="Телефон контрагента",
        p_mobile="Мобильный контрагента",
        p_email="E-mail контрагента",
        customer_dir="Руководитель контрагента",
        p_print_dir="Руководитель контрагента (инициалы)",
        contract_name="Номер договора",
        contract_date_start="Дата начала договора",
        contract_date_end="Дата окончания договора",
        order_date="Дата заказа",
        order_line=ReportList(
            "Строки заказов по договору",
            index="№",
            name="Наименование",
            product_uom_qty="Кол-во",
            price_unit="Цена",
            price_total="Сумма",
        ),
        amount_tax="НДС по заказам",
        amount_total="Сумма по заказам",
    )
    async def contract_data(env: "Environment", record_id: int) -> dict:
        """Данные образцов договоров (contract). Ключи = теги шаблонов."""
        contract = await env.models.contract.search_one(
            filter=[("id", "=", record_id)],
            fields=[
                "id",
                "name",
                "date_start",
                "date_end",
                "partner_id",
                "company_id",
            ],
            fields_nested={
                "partner_id": {"fields": REQUISITE_FIELDS},
                "company_id": {"fields": REQUISITE_FIELDS + ["chief_id"]},
            },
        )
        if not contract:
            raise ValueError(f"Contract #{record_id} not found")

        company = contract.company_id
        partner = contract.partner_id

        # Руководитель — связь внутри вложенной компании приходит числом
        signers = await _by_id(
            env.models.user,
            [company] if company else [],
            ("chief_id",),
            ["id", "name"],
        )
        chief = signers.get(_rel_id(company.chief_id)) if company else None
        chief_name = (chief.name or "") if chief else ""

        # Заказы по договору и их строки — для договора-счёта и приложений
        sales = await env.models.sale.search(
            filter=[("contract_id", "=", record_id)],
            fields=[
                "id",
                "date_order",
                "amount_tax",
                "amount_total",
                "order_line_ids",
            ],
            fields_nested={
                "order_line_ids": {
                    "fields": [
                        "id",
                        "product_uom_qty",
                        "price_unit",
                        "price_total",
                        "product_id",
                        "product_uom_id",
                        "notes",
                    ]
                }
            },
        )
        raw_lines = [
            line for sale in sales for line in (sale.order_line_ids or [])
        ]
        products = await _by_id(
            env.models.product, raw_lines, ("product_id",), ["id", "name"]
        )
        uoms = await _by_id(
            env.models.uom, raw_lines, ("product_uom_id",), ["id", "name"]
        )
        order_line = []
        for line in raw_lines:
            product = products.get(_rel_id(line.product_id))
            uom = uoms.get(_rel_id(line.product_uom_id))
            name = (product.name if product else "") or line.notes or ""
            order_line.append(
                {
                    "index": len(order_line) + 1,
                    "name": name,
                    # Образцы берут товар и единицу парами (id, имя), как
                    # Many2one в Odoo: {{line.product_id[1]}}
                    "product_id": (product.id if product else None, name),
                    "product_uom": (
                        (uom.id, uom.name or "") if uom else (None, "")
                    ),
                    "product_uom_qty": float(line.product_uom_qty or 0),
                    "price_unit": _format_money(float(line.price_unit or 0)),
                    "price_total": _format_money(float(line.price_total or 0)),
                    "mt_line_duration": "",
                }
            )
        dates = sorted(
            str(sale.date_order) for sale in sales if sale.date_order
        )
        order_date = dates[-1] if dates else date.today().isoformat()

        return {
            **_party(company, "c_", "c_"),
            "c_phone": "",
            "c_mobile": "",
            "c_email": "",
            "our_dir": chief_name,
            "c_print_dir": _initials(chief_name),
            "contract_company_name": (company.name or "") if company else "",
            **_party(partner, "partner_", "p_"),
            **await _partner_contacts(
                env, _rel_id(partner) if partner else None
            ),
            "customer_dir": "",
            "p_print_dir": "",
            "contract_name": contract.name or "",
            "contract_date_start": _ru_date(str(contract.date_start or "")),
            "contract_date_end": _ru_date(str(contract.date_end or "")),
            "order_date": _ru_date(order_date),
            "order_line": order_line,
            "amount_tax": _format_money(
                sum(float(s.amount_tax or 0) for s in sales)
            ),
            "amount_total": _format_money(
                sum(float(s.amount_total or 0) for s in sales)
            ),
        }
