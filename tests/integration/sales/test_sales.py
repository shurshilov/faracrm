"""
Integration tests for Sales module.

Tests cover:
- Sale CRUD
- Sale stages
- Sale lines (order items)
- Tax management

Run: pytest tests/integration/sales/test_sales.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration


class TestSaleStages:
    """Tests for SaleStage model."""

    async def test_create_stage(self):
        from backend.base.crm.sales.models.sale_stage import SaleStage

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        s = await SaleStage.get(sid)
        assert s.name == "Draft"

    async def test_create_pipeline(self):
        from backend.base.crm.sales.models.sale_stage import SaleStage

        stages = [
            ("Draft", 1),
            ("Sent", 2),
            ("Confirmed", 3),
            ("Done", 4),
            ("Cancelled", 5),
        ]
        for name, seq in stages:
            await SaleStage.create(SaleStage(name=name, sequence=seq))
        all_s = await SaleStage.search(
            fields=["id", "name", "sequence"],
            sort="sequence",
            order="asc",
        )
        assert len(all_s) == 5
        assert all_s[0].name == "Draft"


class TestSaleCreate:
    """Tests for sale creation."""

    async def test_create_sale_minimal(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.partners.models.partners import Partner

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        pid = await Partner.create(Partner(name="Customer"))
        sale_id = await Sale.create(
            Sale(
                name="SO-0001",
                stage_id=sid,
                partner_id=pid,
            )
        )
        sale = await Sale.get(sale_id)
        assert sale.name == "SO-0001"
        assert sale.active is True

    async def test_create_sale_with_notes(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.partners.models.partners import Partner

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        pid = await Partner.create(Partner(name="Customer"))
        sale_id = await Sale.create(
            Sale(
                name="SO-0002",
                stage_id=sid,
                partner_id=pid,
                notes="Important order — rush delivery",
            )
        )
        sale = await Sale.get(sale_id)
        assert "rush" in sale.notes


class TestSaleRead:
    """Tests for reading sales."""

    async def test_search_sales(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.partners.models.partners import Partner

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        pid = await Partner.create(Partner(name="Customer"))
        for i in range(5):
            await Sale.create(
                Sale(name=f"SO-{i:04d}", stage_id=sid, partner_id=pid)
            )

        sales = await Sale.search(fields=["id", "name"])
        assert len(sales) == 5

    async def test_search_by_partner(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.partners.models.partners import Partner

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        p1 = await Partner.create(Partner(name="Customer A"))
        p2 = await Partner.create(Partner(name="Customer B"))

        await Sale.create(Sale(name="SO-A1", stage_id=sid, partner_id=p1))
        await Sale.create(Sale(name="SO-A2", stage_id=sid, partner_id=p1))
        await Sale.create(Sale(name="SO-B1", stage_id=sid, partner_id=p2))

        a_sales = await Sale.search(
            fields=["id", "name"],
            filter=[("partner_id", "=", p1)],
        )
        assert len(a_sales) == 2


class TestSaleUpdate:
    """Tests for updating sales."""

    async def test_move_stage(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.partners.models.partners import Partner

        s1 = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        s2 = await SaleStage.create(SaleStage(name="Confirmed", sequence=2))
        pid = await Partner.create(Partner(name="Customer"))

        sale_id = await Sale.create(
            Sale(name="SO-MOVE", stage_id=s1, partner_id=pid)
        )
        sale = await Sale.get(sale_id)
        await sale.update(Sale(stage_id=s2))

        updated = await Sale.get(sale_id, fields=["id", "stage_id"])
        assert updated.stage_id.id == s2

    async def test_deactivate_sale(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.partners.models.partners import Partner

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        pid = await Partner.create(Partner(name="Customer"))

        sale_id = await Sale.create(
            Sale(name="SO-ARCH", stage_id=sid, partner_id=pid)
        )
        sale = await Sale.get(sale_id)
        await sale.update(Sale(active=False))

        updated = await Sale.get(sale_id)
        assert updated.active is False


class TestSaleDelete:
    """Tests for deleting sales."""

    async def test_delete_sale(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.partners.models.partners import Partner

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        pid = await Partner.create(Partner(name="Customer"))
        sale_id = await Sale.create(
            Sale(name="SO-DEL", stage_id=sid, partner_id=pid)
        )
        sale = await Sale.get(sale_id)
        await sale.delete()
        assert await Sale.get_or_none(sale_id) is None


# ====================
# Sale Lines
# ====================


class TestSaleLines:
    """Tests for SaleLine model."""

    async def test_create_sale_line(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.sales.models.sale_line import SaleLine
        from backend.base.crm.partners.models.partners import Partner
        from backend.base.crm.products.models.product import Product

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        pid = await Partner.create(Partner(name="Customer"))
        prod_id = await Product.create(Product(name="Widget", list_price=50.0))
        sale_id = await Sale.create(
            Sale(name="SO-LINE", stage_id=sid, partner_id=pid)
        )

        line_id = await SaleLine.create(
            SaleLine(
                sale_id=sale_id,
                product_id=prod_id,
                name="Widget",
                quantity=10,
                price_unit=50.0,
            )
        )

        line = await SaleLine.get(line_id)
        assert line.quantity == 10
        assert line.price_unit == pytest.approx(50.0, abs=0.01)

    async def test_sale_with_multiple_lines(self):
        from backend.base.crm.sales.models.sale import Sale
        from backend.base.crm.sales.models.sale_stage import SaleStage
        from backend.base.crm.sales.models.sale_line import SaleLine
        from backend.base.crm.partners.models.partners import Partner
        from backend.base.crm.products.models.product import Product

        sid = await SaleStage.create(SaleStage(name="Draft", sequence=1))
        pid = await Partner.create(Partner(name="Customer"))
        sale_id = await Sale.create(
            Sale(name="SO-MULTI", stage_id=sid, partner_id=pid)
        )

        for i in range(3):
            prod_id = await Product.create(
                Product(name=f"Item {i}", list_price=float(10 * (i + 1)))
            )
            await SaleLine.create(
                SaleLine(
                    sale_id=sale_id,
                    product_id=prod_id,
                    name=f"Item {i}",
                    quantity=i + 1,
                    price_unit=float(10 * (i + 1)),
                )
            )

        lines = await SaleLine.search(
            fields=["id", "name"],
            filter=[("sale_id", "=", sale_id)],
        )
        assert len(lines) == 3


# ====================
# Tax Tests
# ====================


class TestTax:
    """Tests for Tax model."""

    async def test_create_tax(self):
        from backend.base.crm.sales.models.tax import Tax

        tid = await Tax.create(Tax(name="VAT 20%", amount=20.0))
        t = await Tax.get(tid)
        assert t.name == "VAT 20%"
        assert t.amount == pytest.approx(20.0, abs=0.01)

    async def test_multiple_taxes(self):
        from backend.base.crm.sales.models.tax import Tax

        await Tax.create(Tax(name="VAT 20%", amount=20.0))
        await Tax.create(Tax(name="VAT 10%", amount=10.0))
        await Tax.create(Tax(name="No Tax", amount=0.0))
        taxes = await Tax.search(fields=["id", "name", "amount"])
        assert len(taxes) == 3
