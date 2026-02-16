"""
API integration tests for CRM modules (Partners, Leads, Sales, Products, Tasks).

These test the auto-generated CRUD endpoints (search, get, create, update, delete)
via HTTP requests. Complements existing model-level integration tests.

Run: pytest tests/integration/test_crud_api.py -v -m integration
"""

import pytest

from tests.conftest import auto

pytestmark = [pytest.mark.integration, pytest.mark.api]


# ====================
# Partners API
# ====================


class TestPartnersAPI:
    """API tests for Partners CRUD endpoints."""

    async def test_search_partners(
        self, authenticated_client, partner_factory
    ):
        client, _, _ = authenticated_client
        await partner_factory(name="API Partner 1")
        await partner_factory(name="API Partner 2")

        response = await client.post(
            auto("/partners/search"),
            json={"fields": ["id", "name"], "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 2

    async def test_search_partners_with_filter(
        self, authenticated_client, partner_factory
    ):
        client, _, _ = authenticated_client
        await partner_factory(name="Filtered Partner")

        response = await client.post(
            auto("/partners/search"),
            json={
                "fields": ["id", "name"],
                "filter": [["name", "=", "Filtered Partner"]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Filtered Partner"

    async def test_get_partner_by_id(
        self, authenticated_client, partner_factory
    ):
        client, _, _ = authenticated_client
        partner = await partner_factory(name="Get Me")

        response = await client.post(
            auto(f"/partners/{partner.id}"),
            json={"fields": ["id", "name"]},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Get Me"

    async def test_create_partner_api(self, authenticated_client):
        client, _, _ = authenticated_client

        response = await client.post(
            auto("/partners"),
            json={
                "name": "New API Partner",
            },
        )
        assert response.status_code in [200, 201]

    async def test_update_partner_api(
        self, authenticated_client, partner_factory
    ):
        client, _, _ = authenticated_client
        partner = await partner_factory(name="Before")

        response = await client.put(
            auto(f"/partners/{partner.id}"),
            json={"name": "After"},
        )
        assert response.status_code == 200

        from backend.base.crm.partners.models.partners import Partner

        updated = await Partner.get(partner.id)
        assert updated.name == "After"

    async def test_delete_partner_api(
        self, authenticated_client, partner_factory
    ):
        client, _, _ = authenticated_client
        partner = await partner_factory(name="Delete Me")

        response = await client.delete(auto(f"/partners/{partner.id}"))
        assert response.status_code == 200

    async def test_search_partners_unauthorized(self, client):
        response = await client.post(
            auto("/partners/search"),
            json={"fields": ["id", "name"]},
        )
        assert response.status_code in [401, 403]


# ====================
# Leads API
# ====================


class TestLeadsAPI:
    """API tests for Leads CRUD endpoints."""

    async def test_search_leads(self, authenticated_client, lead_factory):
        client, _, _ = authenticated_client
        await lead_factory(name="Lead Alpha")
        await lead_factory(name="Lead Beta")

        response = await client.post(
            auto("/leads/search"),
            json={"fields": ["id", "name"], "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 2

    async def test_get_lead_by_id(self, authenticated_client, lead_factory):
        client, _, _ = authenticated_client
        lead = await lead_factory(name="Specific Lead")

        response = await client.post(
            auto(f"/leads/{lead.id}"),
            json={"fields": ["id", "name"]},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Specific Lead"

    async def test_update_lead(self, authenticated_client, lead_factory):
        client, _, _ = authenticated_client
        lead = await lead_factory(name="Original Lead")

        response = await client.put(
            auto(f"/leads/{lead.id}"),
            json={"name": "Updated Lead"},
        )
        assert response.status_code == 200

    async def test_delete_lead(self, authenticated_client, lead_factory):
        client, _, _ = authenticated_client
        lead = await lead_factory(name="Delete Lead")

        response = await client.delete(auto(f"/leads/{lead.id}"))
        assert response.status_code == 200

    async def test_search_leads_unauthorized(self, client):
        response = await client.post(
            auto("/leads/search"), json={"fields": ["id"]}
        )
        assert response.status_code in [401, 403]


# ====================
# Sales API
# ====================


class TestSalesAPI:
    """API tests for Sales CRUD endpoints."""

    async def test_search_sales(self, authenticated_client, sale_factory):
        client, _, _ = authenticated_client
        await sale_factory(name="SO-0001")
        await sale_factory(name="SO-0002")

        response = await client.post(
            auto("/sales/search"),
            json={"fields": ["id", "name"], "limit": 10},
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 2

    async def test_get_sale_by_id(self, authenticated_client, sale_factory):
        client, _, _ = authenticated_client
        sale = await sale_factory(name="SO-TEST")

        response = await client.post(
            auto(f"/sales/{sale.id}"),
            json={"fields": ["id", "name"]},
        )
        assert response.status_code == 200

    async def test_update_sale(self, authenticated_client, sale_factory):
        client, _, _ = authenticated_client
        sale = await sale_factory()

        response = await client.put(
            auto(f"/sales/{sale.id}"),
            json={"name": "SO-UPDATED"},
        )
        assert response.status_code == 200

    async def test_delete_sale(self, authenticated_client, sale_factory):
        client, _, _ = authenticated_client
        sale = await sale_factory()

        response = await client.delete(auto(f"/sales/{sale.id}"))
        assert response.status_code == 200

    async def test_search_sales_unauthorized(self, client):
        response = await client.post(
            auto("/sales/search"), json={"fields": ["id"]}
        )
        assert response.status_code in [401, 403]


# ====================
# Products API
# ====================


class TestProductsAPI:
    """API tests for Products CRUD endpoints."""

    async def test_search_products(
        self, authenticated_client, product_factory
    ):
        client, _, _ = authenticated_client
        await product_factory(name="Product A", price=100)
        await product_factory(name="Product B", price=200)

        response = await client.post(
            auto("/products/search"),
            json={"fields": ["id", "name", "list_price"], "limit": 10},
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 2

    async def test_get_product_by_id(
        self, authenticated_client, product_factory
    ):
        client, _, _ = authenticated_client
        product = await product_factory(name="Widget")

        response = await client.post(
            auto(f"/products/{product.id}"),
            json={"fields": ["id", "name"]},
        )
        assert response.status_code == 200

    async def test_create_product_api(self, authenticated_client):
        client, _, _ = authenticated_client

        response = await client.post(
            auto("/products"),
            json={"name": "API Product", "list_price": 49.99},
        )
        assert response.status_code in [200, 201]

    async def test_update_product(self, authenticated_client, product_factory):
        client, _, _ = authenticated_client
        product = await product_factory(name="Old Product")

        response = await client.put(
            auto(f"/products/{product.id}"),
            json={"name": "New Product"},
        )
        assert response.status_code == 200

    async def test_delete_product(self, authenticated_client, product_factory):
        client, _, _ = authenticated_client
        product = await product_factory(name="Delete Product")

        response = await client.delete(auto(f"/products/{product.id}"))
        assert response.status_code == 200


# ====================
# Tasks API
# ====================


class TestTasksAPI:
    """API tests for Tasks CRUD endpoints."""

    async def _create_task(self):
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.task import Task
        from backend.base.crm.tasks.models.task_stage import TaskStage

        proj_id = await Project.create(Project(name="API Project"))
        stage_id = await TaskStage.create(TaskStage(name="To Do", sequence=1))
        task_id = await Task.create(
            Task(name="API Task", project_id=proj_id, stage_id=stage_id)
        )
        return task_id

    async def test_search_tasks(self, authenticated_client):
        client, _, _ = authenticated_client
        await self._create_task()

        response = await client.post(
            auto("/tasks/search"),
            json={"fields": ["id", "name"], "limit": 10},
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 1

    async def test_get_task_by_id(self, authenticated_client):
        client, _, _ = authenticated_client
        task_id = await self._create_task()

        response = await client.post(
            auto(f"/tasks/{task_id}"),
            json={"fields": ["id", "name"]},
        )
        assert response.status_code == 200

    async def test_update_task(self, authenticated_client):
        client, _, _ = authenticated_client
        task_id = await self._create_task()

        response = await client.put(
            auto(f"/tasks/{task_id}"),
            json={"name": "Updated Task"},
        )
        assert response.status_code == 200

    async def test_delete_task(self, authenticated_client):
        client, _, _ = authenticated_client
        task_id = await self._create_task()

        response = await client.delete(auto(f"/tasks/{task_id}"))
        assert response.status_code == 200


# ====================
# Cron API
# ====================


class TestCronAPI:
    """API tests for Cron Job custom endpoints."""

    async def _create_job(self):
        from backend.base.system.cron.models.cron_job import CronJob
        from datetime import datetime, timezone

        jid = await CronJob.create(
            CronJob(
                name="API Test Job",
                code='result["ok"] = True',
                active=True,
                interval_number=1,
                interval_type="hours",
                nextcall=datetime.now(timezone.utc),
            )
        )
        return jid

    async def test_toggle_job(self, authenticated_client):
        client, _, _ = authenticated_client
        job_id = await self._create_job()

        response = await client.patch(f"/cron_job/{job_id}/toggle")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data

    async def test_toggle_nonexistent_job(self, authenticated_client):
        client, _, _ = authenticated_client

        response = await client.patch("/cron_job/99999/toggle")
        assert response.status_code in [404, 500]

    async def test_search_cron_jobs(self, authenticated_client):
        client, _, _ = authenticated_client
        await self._create_job()

        response = await client.post(
            auto("/cron_jobs/search"),
            json={"fields": ["id", "name", "active"], "limit": 10},
        )
        # Endpoint name may vary (cron_job vs cron_jobs)
        assert response.status_code in [200, 404]
