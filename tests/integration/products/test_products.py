"""
Integration tests for Products module.

Tests cover:
- Product CRUD
- Category management
- Unit of measure (Uom)
- Product search and filtering

Run: pytest tests/integration/products/test_products.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration


class TestProductCreate:
    """Tests for product creation."""

    async def test_create_product_minimal(self):
        from backend.base.crm.products.models.product import Product

        pid = await Product.create(Product(name="Widget"))
        p = await Product.get(pid)
        assert p.name == "Widget"

    async def test_create_product_with_price(self):
        from backend.base.crm.products.models.product import Product

        pid = await Product.create(
            Product(
                name="Premium Widget",
                list_price=299.99,
            )
        )
        p = await Product.get(pid)
        assert p.list_price == pytest.approx(299.99, abs=0.01)

    async def test_create_product_types(self):
        from backend.base.crm.products.models.product import Product

        goods_id = await Product.create(Product(name="Physical", type="consu"))
        service_id = await Product.create(
            Product(name="Service", type="service")
        )

        goods = await Product.get(goods_id)
        service = await Product.get(service_id)
        assert goods.type == "consu"
        assert service.type == "service"

    async def test_create_product_default_type(self):
        from backend.base.crm.products.models.product import Product

        pid = await Product.create(Product(name="Default Type"))
        p = await Product.get(pid)
        assert p.type == "consu"

    async def test_create_product_with_description(self):
        from backend.base.crm.products.models.product import Product

        pid = await Product.create(
            Product(
                name="Described Product",
                description="A very detailed product description.",
            )
        )
        p = await Product.get(pid)
        assert p.description == "A very detailed product description."


class TestProductRead:
    """Tests for reading products."""

    async def test_search_products(self):
        from backend.base.crm.products.models.product import Product

        for i in range(5):
            await Product.create(Product(name=f"Product {i}"))
        prods = await Product.search(fields=["id", "name"])
        assert len(prods) == 5

    async def test_search_by_type(self):
        from backend.base.crm.products.models.product import Product

        await Product.create(Product(name="Goods 1", type="consu"))
        await Product.create(Product(name="Goods 2", type="consu"))
        await Product.create(Product(name="Service 1", type="service"))

        goods = await Product.search(
            fields=["id", "name"],
            filter=[("type", "=", "consu")],
        )
        assert len(goods) == 2

    async def test_count_products(self):
        from backend.base.crm.products.models.product import Product

        for i in range(7):
            await Product.create(Product(name=f"Count {i}"))
        count = await Product.table_len()
        assert count == 7


class TestProductUpdate:
    """Tests for updating products."""

    async def test_update_price(self):
        from backend.base.crm.products.models.product import Product

        pid = await Product.create(Product(name="Repriced", list_price=100.0))
        p = await Product.get(pid)
        await p.update(Product(list_price=150.0))
        updated = await Product.get(pid)
        assert updated.list_price == pytest.approx(150.0, abs=0.01)

    async def test_deactivate_product(self):
        from backend.base.crm.products.models.product import Product

        pid = await Product.create(Product(name="Active Prod", active=True))
        p = await Product.get(pid)
        await p.update(Product(active=False))
        updated = await Product.get(pid)
        assert updated.active is False


class TestProductDelete:
    """Tests for deleting products."""

    async def test_delete_product(self):
        from backend.base.crm.products.models.product import Product

        pid = await Product.create(Product(name="Del Me"))
        p = await Product.get(pid)
        await p.delete()
        assert await Product.get_or_none(pid) is None


# ====================
# Category Tests
# ====================


class TestCategory:
    """Tests for product categories."""

    async def test_create_category(self):
        from backend.base.crm.products.models.category import Category

        cid = await Category.create(Category(name="Electronics"))
        c = await Category.get(cid)
        assert c.name == "Electronics"

    async def test_search_categories(self):
        from backend.base.crm.products.models.category import Category

        for name in ["Electronics", "Clothing", "Food"]:
            await Category.create(Category(name=name))
        cats = await Category.search(fields=["id", "name"])
        assert len(cats) == 3

    async def test_product_with_category(self):
        from backend.base.crm.products.models.product import Product
        from backend.base.crm.products.models.category import Category

        cid = await Category.create(Category(name="Gadgets"))
        pid = await Product.create(
            Product(name="Smartphone", category_id=Category(id=cid))
        )
        p = await Product.get(
            pid,
            fields=["id", "name", "category_id"],
            fields_nested={"category_id": ["id"]},
        )
        assert p.category_id.id == cid


# ====================
# UoM Tests
# ====================


class TestUom:
    """Tests for units of measure."""

    async def test_create_uom(self):
        from backend.base.crm.products.models.uom import Uom

        uid = await Uom.create(Uom(name="Piece"))
        u = await Uom.get(uid)
        assert u.name == "Piece"

    async def test_multiple_uoms(self):
        from backend.base.crm.products.models.uom import Uom

        for name in ["Piece", "Kg", "Liter", "Box"]:
            await Uom.create(Uom(name=name))
        uoms = await Uom.search(fields=["id", "name"])
        assert len(uoms) == 4
