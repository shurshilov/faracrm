import unittest
from fastapi.testclient import TestClient
from backend.main import app
import httpx


class TestRules(unittest.IsolatedAsyncioTestCase):
    URL = "http://127.0.0.1:8090"
    URL_SIGNIN = "/signin"
    TOKEN = ""
    create_id = None
    create_obj = {}

    # связанные данные для теста
    role_id = None
    role_name = None

    async def test_01_sigin(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            response = client.post(
                f"{self.URL_SIGNIN}",
                json={"login": "admin", "password": "12345678!Aaa"},
            )
            json = response.json()
            assert response.status_code in [200]
            self.__class__.TOKEN = f"{json.get('token')}"
            print(self.__class__.TOKEN)

            data = {"name": "test role"}
            response = client.post(
                f"{self.URL}/roles",
                json=data,
                headers={"Authorization": "Bearer " + self.__class__.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.role_id = json.get("id")
            self.__class__.role_name = "test role"

    async def test_02_search(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {
                "fields": ["id"],
                "end": 0,
                "order": "DESC",
                "sort": "id",
                "start": 0,
                "limit": 80,
            }
            response = client.post(
                f"{self.URL}/rules/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [{"name": "id", "type": "Integer"}]

            data["fields"] = ["id", "name"]
            response = client.post(
                f"{self.URL}/rules/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [
                {"name": "id", "type": "Integer"},
                {"name": "name", "type": "Char"},
            ]

            data["order"] = "ASC"
            response = client.post(
                f"{self.URL}/rules/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [
                {"name": "id", "type": "Integer"},
                {"name": "name", "type": "Char"},
            ]

            data["sort"] = "name"
            response = client.post(
                f"{self.URL}/rules/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [
                {"name": "id", "type": "Integer"},
                {"name": "name", "type": "Char"},
            ]

            data["end"] = 20
            response = client.post(
                f"{self.URL}/rules/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [
                {"name": "id", "type": "Integer"},
                {"name": "name", "type": "Char"},
            ]

    async def test_03_create_no_relation_rules(self):
        data = {"name": "auto_test_created", "role_id": self.role_id}

        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            response = client.post(
                f"{self.URL}/rules",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.create_id = json.get("id")

    async def test_04_update_no_relation_rules(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {"name": "auto_test_updated", "role_id": self.role_id}

            response = client.put(
                f"{self.URL}/rules/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]

    async def test_05_read_no_relation_rules(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {"fields": ["id", "name", "role_id"]}
            response = client.post(
                f"{self.URL}/rules/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            print(response)
            assert response == {
                "data": {
                    "id": self.create_id,
                    "name": "auto_test_updated",
                    "role_id": {
                        "id": self.role_id,
                        "name": self.role_name,
                        "model_id": None,
                        "user_ids": None,
                        "acl_ids": None,
                        "rule_ids": None,
                    },
                },
                "fields": {
                    "id": {"name": "id", "type": "Integer"},
                    "name": {"name": "name", "type": "Char"},
                    "role_id": {
                        "name": "role_id",
                        "type": "Many2one",
                        "relatedModel": "roles",
                        "relatedField": "",
                    },
                },
            }

    async def test_06_delete_no_relation_rules(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            if self.create_id:
                data = {"fields": ["id", "name", "role_id"]}
                response = client.post(
                    f"{self.URL}/rules/{self.create_id}",
                    json=data,
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
                response = client.delete(
                    f"{self.URL}/rules/{self.create_id}",
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
            else:
                assert 1 == 2
