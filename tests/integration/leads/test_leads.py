"""
Integration tests for Leads module.

Tests cover:
- Lead CRUD
- Lead stages
- Lead type (lead / opportunity)
- Sales team

Run: pytest tests/integration/leads/test_leads.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration


class TestLeadStages:
    """Tests for LeadStage model."""

    async def test_create_stage(self):
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        s = await LeadStage.get(sid)
        assert s.name == "New"
        assert s.sequence == 1

    async def test_create_pipeline(self):
        from backend.base.crm.leads.models.lead_stage import LeadStage

        stages = [
            ("New", 1),
            ("Qualified", 2),
            ("Proposal", 3),
            ("Won", 4),
            ("Lost", 5),
        ]
        for name, seq in stages:
            await LeadStage.create(LeadStage(name=name, sequence=seq))

        all_stages = await LeadStage.search(
            fields=["id", "name", "sequence"],
            sort="sequence",
            order="asc",
        )
        assert len(all_stages) == 5
        assert all_stages[0].name == "New"
        assert all_stages[-1].name == "Lost"


class TestLeadCreate:
    """Tests for lead creation."""

    async def test_create_lead_minimal(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        lid = await Lead.create(Lead(name="Test Lead", stage_id=sid))

        lead = await Lead.get(lid)
        assert lead.name == "Test Lead"
        assert lead.active is True

    async def test_create_lead_with_partner(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage
        from backend.base.crm.partners.models.partners import Partner

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        pid = await Partner.create(Partner(name="Lead Partner"))
        lid = await Lead.create(
            Lead(
                name="Partner Lead",
                stage_id=sid,
                parent_id=pid,
            )
        )

        lead = await Lead.get(lid, fields=["id", "name", "parent_id"])
        assert lead.parent_id.id == pid

    async def test_create_lead_with_contact_info(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        lid = await Lead.create(
            Lead(
                name="Contact Lead",
                stage_id=sid,
                email="lead@example.com",
                phone="+79001234567",
                website="https://example.com",
            )
        )

        lead = await Lead.get(lid)
        assert lead.email == "lead@example.com"
        assert lead.phone == "+79001234567"
        assert lead.website == "https://example.com"

    async def test_create_lead_types(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))

        lead_id = await Lead.create(
            Lead(name="A Lead", stage_id=sid, type="lead")
        )
        opp_id = await Lead.create(
            Lead(name="An Opp", stage_id=sid, type="opportunity")
        )

        lead = await Lead.get(lead_id)
        opp = await Lead.get(opp_id)
        assert lead.type == "lead"
        assert opp.type == "opportunity"

    async def test_create_lead_default_type(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        lid = await Lead.create(Lead(name="Default Type", stage_id=sid))

        lead = await Lead.get(lid)
        assert lead.type == "lead"


class TestLeadRead:
    """Tests for reading leads."""

    async def test_search_all_leads(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        for i in range(5):
            await Lead.create(Lead(name=f"Lead {i}", stage_id=sid))

        leads = await Lead.search(fields=["id", "name"])
        assert len(leads) == 5

    async def test_search_by_type(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        await Lead.create(Lead(name="Lead 1", stage_id=sid, type="lead"))
        await Lead.create(Lead(name="Lead 2", stage_id=sid, type="lead"))
        await Lead.create(Lead(name="Opp 1", stage_id=sid, type="opportunity"))

        leads = await Lead.search(
            fields=["id", "name"],
            filter=[("type", "=", "lead")],
        )
        assert len(leads) == 2

    async def test_search_by_name_ilike(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        await Lead.create(Lead(name="Acme Project", stage_id=sid))
        await Lead.create(Lead(name="ACME Deal", stage_id=sid))
        await Lead.create(Lead(name="Other Lead", stage_id=sid))

        results = await Lead.search(
            fields=["id", "name"],
            filter=[("name", "ilike", "%acme%")],
        )
        assert len(results) == 2


class TestLeadUpdate:
    """Tests for updating leads."""

    async def test_move_to_next_stage(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        s1 = await LeadStage.create(LeadStage(name="New", sequence=1))
        s2 = await LeadStage.create(LeadStage(name="Qualified", sequence=2))

        lid = await Lead.create(Lead(name="Stage Lead", stage_id=s1))
        lead = await Lead.get(lid)
        await lead.update(Lead(stage_id=s2))

        updated = await Lead.get(lid, fields=["id", "stage_id"])
        assert updated.stage_id.id == s2

    async def test_convert_lead_to_opportunity(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        lid = await Lead.create(
            Lead(name="Convert Me", stage_id=sid, type="lead")
        )

        lead = await Lead.get(lid)
        await lead.update(Lead(type="opportunity"))

        updated = await Lead.get(lid)
        assert updated.type == "opportunity"

    async def test_deactivate_lead(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        lid = await Lead.create(Lead(name="Archive Me", stage_id=sid))

        lead = await Lead.get(lid)
        await lead.update(Lead(active=False))

        updated = await Lead.get(lid)
        assert updated.active is False


class TestLeadDelete:
    """Tests for deleting leads."""

    async def test_delete_lead(self):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        sid = await LeadStage.create(LeadStage(name="New", sequence=1))
        lid = await Lead.create(Lead(name="Delete Me", stage_id=sid))

        lead = await Lead.get(lid)
        await lead.delete()
        assert await Lead.get_or_none(lid) is None


# ====================
# Team CRM Tests
# ====================


class TestTeamCrm:
    """Tests for TeamCrm (sales teams)."""

    async def test_create_team(self):
        from backend.base.crm.leads.models.team_crm import TeamCrm

        tid = await TeamCrm.create(TeamCrm(name="Sales Team A"))
        t = await TeamCrm.get(tid)
        assert t.name == "Sales Team A"

    async def test_search_teams(self):
        from backend.base.crm.leads.models.team_crm import TeamCrm

        await TeamCrm.create(TeamCrm(name="Team A"))
        await TeamCrm.create(TeamCrm(name="Team B"))
        teams = await TeamCrm.search(fields=["id", "name"])
        assert len(teams) == 2
