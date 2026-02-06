"""
Integration tests for Partners module.

Tests cover:
- Partner CRUD
- Contact management
- Contact types
- Parent/child hierarchy
- Partner search and filtering

Run: pytest tests/integration/partners/test_partners.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration


# ====================
# Partner CRUD
# ====================


class TestPartnerCreate:
    """Tests for partner creation."""

    async def test_create_partner_minimal(self):
        """Test creating partner with minimal fields."""
        from backend.base.crm.partners.models.partners import Partner

        partner_id = await Partner.create(Partner(name="Test Partner"))
        assert partner_id > 0

        partner = await Partner.get(partner_id)
        assert partner.name == "Test Partner"
        assert partner.active is True

    async def test_create_customer(self):
        """Test creating customer partner."""
        from backend.base.crm.partners.models.partners import Partner

        pid = await Partner.create(
            Partner(
                name="Customer Corp",
                is_customer=True,
                is_supplier=False,
            )
        )

        p = await Partner.get(pid)
        assert p.is_customer is True
        assert p.is_supplier is False

    async def test_create_supplier(self):
        """Test creating supplier partner."""
        from backend.base.crm.partners.models.partners import Partner

        pid = await Partner.create(
            Partner(
                name="Supplier Inc",
                is_customer=False,
                is_supplier=True,
            )
        )

        p = await Partner.get(pid)
        assert p.is_customer is False
        assert p.is_supplier is True

    async def test_create_partner_hierarchy(self):
        """Test creating parent/child partners."""
        from backend.base.crm.partners.models.partners import Partner

        parent_id = await Partner.create(Partner(name="Parent Corp"))
        child_id = await Partner.create(
            Partner(
                name="Child Division",
                parent_id=parent_id,
            )
        )

        child = await Partner.get(child_id, fields=["id", "name", "parent_id"])
        assert child.parent_id.id == parent_id

    async def test_create_partner_bulk(self):
        """Test bulk creating partners."""
        from backend.base.crm.partners.models.partners import Partner

        partners = [Partner(name=f"Bulk Partner {i}") for i in range(10)]
        result = await Partner.create_bulk(partners)
        assert len(result) == 10


class TestPartnerRead:
    """Tests for reading partners."""

    async def test_search_partners(self):
        """Test searching partners."""
        from backend.base.crm.partners.models.partners import Partner

        await Partner.create(Partner(name="Alpha Corp"))
        await Partner.create(Partner(name="Beta Ltd"))
        await Partner.create(Partner(name="Gamma Inc"))

        partners = await Partner.search(fields=["id", "name"])
        assert len(partners) == 3

    async def test_search_by_name_ilike(self):
        """Test case-insensitive name search."""
        from backend.base.crm.partners.models.partners import Partner

        await Partner.create(Partner(name="Acme Corporation"))
        await Partner.create(Partner(name="acme industries"))
        await Partner.create(Partner(name="Other Company"))

        partners = await Partner.search(
            fields=["id", "name"],
            filter=[("name", "ilike", "%acme%")],
        )
        assert len(partners) == 2

    async def test_search_active_only(self):
        """Test searching active partners only."""
        from backend.base.crm.partners.models.partners import Partner

        await Partner.create(Partner(name="Active", active=True))
        await Partner.create(Partner(name="Inactive", active=False))

        active = await Partner.search(
            fields=["id", "name"],
            filter=[("active", "=", True)],
        )
        assert len(active) == 1
        assert active[0].name == "Active"

    async def test_search_with_sort_and_pagination(self):
        """Test sorted and paginated search."""
        from backend.base.crm.partners.models.partners import Partner

        for i in range(20):
            await Partner.create(Partner(name=f"Partner {i:03d}"))

        page1 = await Partner.search(
            fields=["id", "name"],
            sort="name",
            order="asc",
            start=0,
            end=5,
        )
        page2 = await Partner.search(
            fields=["id", "name"],
            sort="name",
            order="asc",
            start=5,
            end=10,
        )

        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[-1].name < page2[0].name


class TestPartnerUpdate:
    """Tests for updating partners."""

    async def test_update_partner_name(self):
        """Test updating partner name."""
        from backend.base.crm.partners.models.partners import Partner

        pid = await Partner.create(Partner(name="Old Name"))
        p = await Partner.get(pid)

        await p.update(Partner(name="New Name"))

        updated = await Partner.get(pid)
        assert updated.name == "New Name"

    async def test_deactivate_partner(self):
        """Test deactivating partner."""
        from backend.base.crm.partners.models.partners import Partner

        pid = await Partner.create(Partner(name="Active Partner", active=True))
        p = await Partner.get(pid)

        await p.update(Partner(active=False))

        updated = await Partner.get(pid)
        assert updated.active is False

    async def test_bulk_update_partners(self):
        """Test bulk updating partners."""
        from backend.base.crm.partners.models.partners import Partner

        ids = []
        for i in range(5):
            pid = await Partner.create(Partner(name=f"Bulk {i}", active=True))
            ids.append(pid)

        await Partner.update_bulk(ids=ids, payload=Partner(active=False))

        for pid in ids:
            p = await Partner.get(pid)
            assert p.active is False


class TestPartnerDelete:
    """Tests for deleting partners."""

    async def test_delete_partner(self):
        """Test deleting partner."""
        from backend.base.crm.partners.models.partners import Partner

        pid = await Partner.create(Partner(name="To Delete"))
        p = await Partner.get(pid)
        await p.delete()

        assert await Partner.get_or_none(pid) is None

    async def test_delete_bulk_partners(self):
        """Test bulk deleting partners."""
        from backend.base.crm.partners.models.partners import Partner

        ids = [
            await Partner.create(Partner(name=f"Del {i}")) for i in range(5)
        ]
        await Partner.delete_bulk(ids[:3])

        for i in range(3):
            assert await Partner.get(ids[i]) is None
        for i in range(3, 5):
            assert await Partner.get(ids[i]) is not None


# ====================
# Contact Types
# ====================


class TestContactTypes:
    """Tests for ContactType model."""

    async def test_create_contact_type(self):
        """Test creating contact type."""
        from backend.base.crm.partners.models.contact_type import ContactType

        ct_id = await ContactType.create(ContactType(name="Phone"))
        ct = await ContactType.get(ct_id)
        assert ct.name == "Phone"

    async def test_create_multiple_types(self):
        """Test creating multiple contact types."""
        from backend.base.crm.partners.models.contact_type import ContactType

        types = ["Phone", "Email", "Telegram", "WhatsApp"]
        for t in types:
            await ContactType.create(ContactType(name=t))

        all_types = await ContactType.search(fields=["id", "name"])
        assert len(all_types) == 4


# ====================
# Contacts
# ====================


class TestContacts:
    """Tests for Contact model."""

    async def test_create_contact_for_partner(self):
        """Test creating contact linked to partner."""
        from backend.base.crm.partners.models.partners import Partner
        from backend.base.crm.partners.models.contact import Contact
        from backend.base.crm.partners.models.contact_type import ContactType

        ct_id = await ContactType.create(ContactType(name="Phone"))
        pid = await Partner.create(Partner(name="Contact Test"))

        c_id = await Contact.create(
            Contact(
                name="+79001234567",
                contact_type_id=ct_id,
                partner_id=pid,
                is_primary=True,
            )
        )

        c = await Contact.get(c_id)
        assert c.name == "+79001234567"
        assert c.is_primary is True

    async def test_partner_multiple_contacts(self):
        """Test partner with multiple contacts."""
        from backend.base.crm.partners.models.partners import Partner
        from backend.base.crm.partners.models.contact import Contact
        from backend.base.crm.partners.models.contact_type import ContactType

        phone_id = await ContactType.create(ContactType(name="Phone"))
        email_id = await ContactType.create(ContactType(name="Email"))
        pid = await Partner.create(Partner(name="Multi Contact"))

        await Contact.create(
            Contact(
                name="+79001111111",
                contact_type_id=phone_id,
                partner_id=pid,
                is_primary=True,
            )
        )
        await Contact.create(
            Contact(
                name="test@test.com",
                contact_type_id=email_id,
                partner_id=pid,
                is_primary=False,
            )
        )

        contacts = await Contact.search(
            fields=["id", "name"],
            filter=[("partner_id", "=", pid)],
        )
        assert len(contacts) == 2
