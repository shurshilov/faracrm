"""
Integration tests: Lead → Sale link (Lead.create_sale, Sale.lead_id).

Sale.lead_id is added to Sale by the leads module (@extend, leads/models/sale_ext.py);
Lead.create_sale copies the base fields and links the new sale to the lead.

Run: pytest tests/integration/leads/test_lead_sale_link.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration

from backend.base.crm.leads.models.lead_stage import LeadStage
from backend.base.crm.leads.models.leads import Lead
from backend.base.crm.partners.models.partners import Partner
from backend.base.crm.sales.models.sale import Sale
from backend.base.crm.sales.models.sale_stage import SaleStage


def _rel_id(value):
    """Many2one после get/search — объект со .id либо голый id."""
    return getattr(value, "id", value)


class TestCreateSaleFromLead:
    # test_env: Sale._default_name читает sequence через env.apps.db.get_session().

    async def test_copies_base_fields_and_links_lead(self, test_env):
        stage_id = await LeadStage.create(LeadStage(name="Новый", sequence=10))
        await SaleStage.create(SaleStage(name="Отправлено", sequence=20))
        draft_id = await SaleStage.create(
            SaleStage(name="Черновик", sequence=10)
        )
        pid = await Partner.create(Partner(name="Клиент"))
        lid = await Lead.create(
            Lead(
                name="Заявка с сайта",
                stage_id=stage_id,
                partner_id=pid,
                notes="срочно",
            )
        )

        lead = await Lead.get(lid)
        sale_id = await lead.create_sale()

        sales = await Sale.search(
            filter=[("id", "=", sale_id)],
            fields=[
                "id",
                "lead_id",
                "partner_id",
                "stage_id",
                "origin",
                "notes",
            ],
        )
        assert len(sales) == 1
        sale = sales[0]
        assert _rel_id(sale.lead_id) == lid
        assert _rel_id(sale.partner_id) == pid
        # Первая по порядку активная стадия, а не «первая найденная».
        assert _rel_id(sale.stage_id) == draft_id
        assert sale.origin == "Заявка с сайта"
        assert sale.notes == "срочно"

    async def test_repeat_orders_one_lead_many_sales(self, test_env):
        stage_id = await LeadStage.create(LeadStage(name="Новый", sequence=10))
        await SaleStage.create(SaleStage(name="Черновик", sequence=10))
        lid = await Lead.create(Lead(name="Заявка", stage_id=stage_id))
        lead = await Lead.get(lid)

        await lead.create_sale()
        await lead.create_sale()

        assert await Sale.search_count(filter=[("lead_id", "=", lid)]) == 2
