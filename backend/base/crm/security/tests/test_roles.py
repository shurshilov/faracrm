import unittest
from fastapi.testclient import TestClient
from backend.main import app
import httpx


class TestRoles(unittest.IsolatedAsyncioTestCase):
    URL = "http://127.0.0.1:8090"
    URL_SIGNIN = "/signin"
    TOKEN = ""
    create_id = None
    create_obj = {}
    client = TestClient(app)
    # связанные данные для теста
    model_id = None
    model_id2 = None
    model_name = None
    model_name2 = None

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

            data = {"name": "test model"}
            response = client.post(
                f"{self.URL}/models",
                json=data,
                headers={"Authorization": "Bearer " + self.__class__.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.model_id = json.get("id")
            self.__class__.model_name = "test model"

            data = {"name": "test model2"}
            response = client.post(
                f"{self.URL}/models",
                json=data,
                headers={"Authorization": "Bearer " + self.__class__.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.model_id2 = json.get("id")
            self.__class__.model_name2 = "test model2"

    async def test_02_search_roles(self):
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
                f"{self.URL}/roles/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [{"name": "id", "type": "Integer"}]

            data["fields"] = ["id", "name"]
            response = client.post(
                f"{self.URL}/roles/search",
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
                f"{self.URL}/roles/search",
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
                f"{self.URL}/roles/search",
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
                f"{self.URL}/roles/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [
                {"name": "id", "type": "Integer"},
                {"name": "name", "type": "Char"},
            ]

    async def test_03_create_no_relation_roles(self):
        data = {"name": "auto_test_created", "model_id": self.model_id}

        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            response = client.post(
                f"{self.URL}/roles",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.create_id = json.get("id")

    async def test_04_update_no_relation_roles(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {"name": "auto_test_updated", "model_id": self.model_id}

            response = client.put(
                f"{self.URL}/roles/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]

    async def test_05_read_no_relation_roles(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {"fields": ["id", "name", "model_id"]}
            response = client.post(
                f"{self.URL}/roles/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response == {
                "data": {
                    "id": self.create_id,
                    "name": "auto_test_updated",
                    "model_id": {"id": self.model_id, "name": self.model_name},
                },
                "fields": {
                    "id": {"name": "id", "type": "Integer"},
                    "name": {"name": "name", "type": "Char"},
                    "model_id": {
                        "name": "model_id",
                        "type": "Many2one",
                        "relatedModel": "models",
                        "relatedField": "",
                    },
                },
            }

    async def test_06_delete_no_relation_roles(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            if self.create_id:
                data = {"fields": ["id", "name", "model_id"]}
                response = client.post(
                    f"{self.URL}/roles/{self.create_id}",
                    json=data,
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
                response = client.delete(
                    f"{self.URL}/roles/{self.create_id}",
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
            else:
                assert 1 == 2

    async def test_07_create_with_relation_roles(self):
        data = {
            "user_ids": {
                "deleted": [],
                "created": [
                    {
                        "email": "auto_test_email",
                        "name": "auto_test_name",
                        "login": "auto_test_login",
                    }
                ],
            },
            "acl_ids": {
                "deleted": [],
                "created": [
                    {
                        "active": False,
                        "name": "auto_test_name",
                        "model_id": self.model_id,
                        "role_id": "VirtualId",
                    }
                ],
            },
            "rule_ids": {
                "deleted": [],
                "created": [{"name": "auto_test_name", "role_id": "VirtualId"}],
            },
            "model_id": self.model_id,
            "name": "auto_test_name",
        }

        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            response = client.post(
                f"{self.URL}/roles",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.create_id = json.get("id")

    async def test_08_read_with_relation_roles(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {
                "fields": [
                    "id",
                    "model_id",
                    "name",
                    {"acl_ids": ["id", "name", "model_id", "role_id"]},
                    {"rule_ids": ["id", "name", "role_id"]},
                    {"user_ids": ["id", "name", "role_ids"]},
                ]
            }
            response = client.post(
                f"{self.URL}/roles/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            self.__class__.create_obj = response["data"]

    async def test_09_update_with_relation_roles(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {
                "name": "auto_test_name_update",
                "model_id": self.model_id2,
                "user_ids": {
                    "unselected": [self.create_obj["user_ids"]["data"][0]["id"]],
                    "created": [
                        {
                            "name": "auto_test_name_update",
                            "email": "auto_test_email_update",
                            "login": "1auto_test_login_update23",
                        }
                    ],
                },
                "acl_ids": {
                    "deleted": [self.create_obj["acl_ids"]["data"][0]["id"]],
                    "created": [
                        {
                            "active": False,
                            "name": "auto_test_name_update",
                            "model_id": self.model_id,
                            "role_id": self.create_id,
                        }
                    ],
                },
                "rule_ids": {
                    "deleted": [self.create_obj["rule_ids"]["data"][0]["id"]],
                    "created": [
                        {"name": "auto_test_name_update", "role_id": self.create_id}
                    ],
                },
            }

            response = client.put(
                f"{self.URL}/roles/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]

    async def test_10_with_no_relation_roles(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            if self.create_id:
                data = {
                    "fields": [
                        "id",
                        "model_id",
                        "name",
                        {"acl_ids": ["id", "name", "model_id", "role_id"]},
                        {"rule_ids": ["id", "name", "role_id"]},
                        {"user_ids": ["id", "name", "role_ids"]},
                    ]
                }
                response = client.post(
                    f"{self.URL}/roles/{self.create_id}",
                    json=data,
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
                response = client.delete(
                    f"{self.URL}/roles/{self.create_id}",
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
            else:
                assert 1 == 2
