import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestUsers(unittest.IsolatedAsyncioTestCase):
    URL = "http://127.0.0.1:8090"
    URL_SIGNIN = "/signin"
    TOKEN = ""
    create_id = None
    create_obj = {}
    # связанные данные для теста
    model_id = None
    model_name = None

    async def test_01_sigin(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            response = client.post(
                f"{self.URL_SIGNIN}",
                json={"login": "admin", "password": "admin"},
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
                f"{self.URL}/users/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [{"name": "id", "type": "Integer"}]

            data["fields"] = ["id", "name"]
            response = client.post(
                f"{self.URL}/users/search",
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
                f"{self.URL}/users/search",
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
                f"{self.URL}/users/search",
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
                f"{self.URL}/users/search",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            assert response["fields"] == [
                {"name": "id", "type": "Integer"},
                {"name": "name", "type": "Char"},
            ]

    async def test_03_create_no_relation_users(self):
        data = {
            "name": "auto_test_created",
            "email": "auto_test_created",
            "login": "auto_test_created",
        }
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            response = client.post(
                f"{self.URL}/users",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.create_id = json.get("id")

    async def test_04_update_no_relation_users(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {
                "name": "auto_test_created",
                "email": "auto_test_created",
                "login": "auto_test_created",
            }

            response = client.put(
                f"{self.URL}/users/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]

    async def test_05_read_no_relation_users(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {"fields": ["id", "name", "login", "email"]}
            response = client.post(
                f"{self.URL}/users/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            print(response)
            assert response == {
                "data": {
                    "id": self.create_id,
                    "name": "auto_test_created",
                    "email": "auto_test_created",
                    "login": "auto_test_created",
                },
                "fields": {
                    "id": {"name": "id", "type": "Integer"},
                    "name": {"name": "name", "type": "Char"},
                    "login": {"name": "login", "type": "Char"},
                    "email": {"name": "email", "type": "Char"},
                },
            }

    async def test_06_delete_no_relation_users(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            if self.create_id:
                data = {"fields": ["id", "name", "login", "email"]}
                response = client.post(
                    f"{self.URL}/users/{self.create_id}",
                    json=data,
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
                response = client.delete(
                    f"{self.URL}/users/{self.create_id}",
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
            else:
                assert 1 == 2

    async def test_07_create_with_relation_users(self):
        data = {
            "role_ids": {
                "deleted": [],
                "created": [
                    {"model_id": self.model_id, "name": "auto_test_created"}
                ],
            },
            "name": "auto_test_created",
            "email": "auto_test_created",
            "login": "auto_test_created",
        }

        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            response = client.post(
                f"{self.URL}/users",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            json = response.json()
            self.__class__.create_id = json.get("id")

    async def test_08_read_with_relation_users(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {
                "fields": [
                    "name",
                    "email",
                    "login",
                    {"role_ids": ["id", "name", "user_ids"]},
                ]
            }
            response = client.post(
                f"{self.URL}/users/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]
            response = response.json()
            self.__class__.create_obj = response["data"]

    async def test_09_update_with_relation_users(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            data = {
                "name": "51",
                "email": "51",
                "login": "51",
                "role_ids": {
                    "deleted": [self.create_obj["role_ids"]["data"][0]["id"]],
                    "created": [{"model_id": self.model_id, "name": "123"}],
                },
            }

            response = client.put(
                f"{self.URL}/users/{self.create_id}",
                json=data,
                headers={"Authorization": "Bearer " + self.TOKEN},
            )
            assert response.status_code in [200]

    async def test_10_delete_with_no_relation_users(self):
        # async with httpx.AsyncClient(verify=False) as client:
        with TestClient(app) as client:
            if self.create_id:
                data = {
                    "fields": [
                        "name",
                        "email",
                        "login",
                        {"role_ids": ["id", "name", "user_ids"]},
                    ]
                }
                response = client.post(
                    f"{self.URL}/users/{self.create_id}",
                    json=data,
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
                response = client.delete(
                    f"{self.URL}/users/{self.create_id}",
                    headers={"Authorization": "Bearer " + self.TOKEN},
                )
                assert response.status_code in [200]
            else:
                assert 1 == 2
