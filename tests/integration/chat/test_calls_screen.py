"""
Integration tests: экран «Звонки» как обычный список модели `call`.

Экран перестал быть кастомной страницей со своим SQL-эндпоинтом: таблицу
отдаёт авто-CRUD (/auto/call/search), а плашки — /telephony/calls/stats по
тому же фильтру. Тесты закрывают то, что могло молча не работать:

  • record_id (запись разговора) проставляется и доезжает до строки списка —
    иначе колонка «Запись» была бы всегда пустой.
  • сводка считается по фильтру таблицы и НЕ зависит от пагинации: limit в
    таблице не должен менять цифры в плашках; чужие поля в фильтре
    отбиваются 400.

Run: pytest tests/integration/chat/test_calls_screen.py -v -m integration
"""

from datetime import datetime

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.crm.chat_phone.models.call import Call
from backend.base.system.dotorm_databases_postgres.app import (
    DotormDatabasesPostgresService,
)
from tests.conftest import auto


@pytest_asyncio.fixture
async def wired_env(app, db_pool):
    """Тот же wiring, что в остальных chat-тестах: модельные внутренности
    ходят в env.apps.db.get_transaction() модуль-глобального env."""
    DotormDatabasesPostgresService().set_pool(db_pool)
    return app.state.env


async def _make_connector() -> int:
    return await ChatConnector.create(
        ChatConnector(name="Asterisk-test", type="phone_asterisk")
    )


async def _make_call(connector_id: int, **overrides) -> int:
    payload = {
        "connector_id": connector_id,
        "uniqueid": "u-1",
        "direction": "incoming",
        "disposition": "answered",
        "number_from": "79990000001",
        "number_to": "101",
        "started_at": datetime(2026, 8, 16, 10, 0, 0),
        "duration": 30,
        "duration_talk": 20,
        "active": True,
    }
    payload.update(overrides)
    return await Call.create(Call(**payload))


async def _attach_recording(env, call_id: int) -> int:
    """Запись разговора — вложение с res_model='call' + ссылка record_id
    (как это делает Call._save_recording)."""
    attachment_id = await Attachment.create(
        Attachment(
            name=f"call_{call_id}.mp3",
            mimetype="audio/mpeg",
            res_model="call",
            res_id=call_id,
            is_voice=True,
        )
    )
    await Call._link_record(env, call_id, attachment_id)
    return attachment_id


class TestCallsList:
    """Реестр звонков читается обычным /auto/call/search."""

    async def test_search_returns_recording(
        self, wired_env, authenticated_client
    ):
        client, _user_id, _token = authenticated_client
        cid = await _make_connector()
        with_record = await _make_call(cid, uniqueid="u-with")
        without_record = await _make_call(cid, uniqueid="u-without")
        att_id = await _attach_recording(wired_env, with_record)

        response = await client.post(
            auto("/call/search"),
            json={
                "fields": ["id", "direction", "started_at", "record_id"],
                "sort": "id",
                "order": "asc",
            },
        )

        assert response.status_code == 200
        rows = {row["id"]: row for row in response.json()["data"]}

        assert rows[with_record]["record_id"]["id"] == att_id
        assert rows[without_record]["record_id"] is None


class TestPeriodFilter:
    """Фильтры периода лежат в saved_filters; границу подставляет фронт
    строкой (ISO), поэтому её должен принимать и поиск."""

    async def test_period_filters_seeded(self, wired_env):
        from backend.base.crm.chat_phone.app import ChatPhoneApp

        await ChatPhoneApp()._init_call_period_filters(wired_env)
        # Повторный прогон ничего не дублирует (идемпотентность).
        await ChatPhoneApp()._init_call_period_filters(wired_env)

        filters = await wired_env.models.saved_filter.search(
            filter=[("model_name", "=", "call")],
            fields=["id", "name", "filter_data", "is_default", "is_global"],
        )

        by_name = {f.name: f for f in filters}
        assert set(by_name) == {
            "Сегодня",
            "Эта неделя",
            "Этот месяц",
            "Этот квартал",
            "Этот год",
        }
        assert by_name["Сегодня"].is_default is True
        assert by_name["Эта неделя"].is_default is False
        assert all(f.is_global for f in filters)
        assert (
            by_name["Сегодня"].filter_data
            == '[["started_at", ">=", "{{today}}"]]'
        )

    @pytest.mark.parametrize(
        "bound",
        [
            "2026-08-15T21:00:00.000Z",  # фильтр периода: Date.toISOString()
            "2026-08-16",  # ручной фильтр по дате (DateInput)
        ],
    )
    async def test_datetime_filter_accepts_iso_string(
        self, wired_env, authenticated_client, bound
    ):
        """Значение приходит строкой (в JSON нет типа «дата»), а драйверу
        в параметр timestamp-колонки нужен datetime."""
        client, _user_id, _token = authenticated_client
        cid = await _make_connector()
        inside = await _make_call(
            cid, uniqueid="p-in", started_at=datetime(2026, 8, 16, 10, 0, 0)
        )
        await _make_call(
            cid, uniqueid="p-out", started_at=datetime(2026, 8, 10, 10, 0, 0)
        )

        response = await client.post(
            auto("/call/search"),
            json={
                "fields": ["id", "started_at"],
                "filter": [["started_at", ">=", bound]],
            },
        )

        assert response.status_code == 200
        assert [row["id"] for row in response.json()["data"]] == [inside]

    async def test_code_like_string_stays_string(
        self, wired_env, authenticated_client
    ):
        """8-значный код в текстовом поле — не дата (fromisoformat принял бы
        его за basic-формат ISO)."""
        client, _user_id, _token = authenticated_client
        cid = await _make_connector()
        call_id = await _make_call(cid, uniqueid="20260816")

        response = await client.post(
            auto("/call/search"),
            json={
                "fields": ["id", "uniqueid"],
                "filter": [["uniqueid", "=", "20260816"]],
            },
        )

        assert response.status_code == 200
        assert [row["id"] for row in response.json()["data"]] == [call_id]


class TestCallsStats:
    """Сводка считается по фильтру таблицы, но без её пагинации."""

    async def _seed(self) -> int:
        cid = await _make_connector()
        await _make_call(
            cid, uniqueid="s-1", direction="incoming", disposition="answered"
        )
        await _make_call(
            cid, uniqueid="s-2", direction="incoming", disposition="no_answer"
        )
        await _make_call(
            cid, uniqueid="s-3", direction="outgoing", disposition="answered"
        )
        await _make_call(
            cid,
            uniqueid="s-4",
            direction="outgoing",
            disposition="busy",
            active=False,
        )
        return cid

    async def test_stats_counts_by_filter(
        self, wired_env, authenticated_client
    ):
        client, _user_id, _token = authenticated_client
        await self._seed()

        response = await client.post(
            "/telephony/calls/stats",
            json={"filter": [["active", "=", True]]},
        )

        assert response.status_code == 200
        stats = response.json()
        assert stats["total"] == 3  # неактивный звонок отфильтрован
        assert stats["answered"] == 2
        assert stats["missed"] == 1
        assert stats["incoming"] == 2
        assert stats["outgoing"] == 1

    async def test_stats_ignore_pagination(
        self, wired_env, authenticated_client
    ):
        """Таблица показывает страницу, плашки — всю выборку под фильтром."""
        client, _user_id, _token = authenticated_client
        await self._seed()
        table_filter = [["active", "=", True]]

        page = await client.post(
            auto("/call/search"),
            json={"fields": ["id"], "filter": table_filter, "limit": 1},
        )
        stats = await client.post(
            "/telephony/calls/stats", json={"filter": table_filter}
        )

        assert len(page.json()["data"]) == 1
        assert stats.json()["total"] == 3

    async def test_stats_without_filter_counts_everything(
        self, wired_env, authenticated_client
    ):
        client, _user_id, _token = authenticated_client
        await self._seed()

        response = await client.post("/telephony/calls/stats", json={})

        assert response.status_code == 200
        assert response.json()["total"] == 4

    async def test_stats_reject_foreign_field(
        self, wired_env, authenticated_client
    ):
        """Фильтр — только по полям звонка."""
        client, _user_id, _token = authenticated_client

        response = await client.post(
            "/telephony/calls/stats",
            json={"filter": [["password_hash", "=", "x"]]},
        )

        assert response.status_code == 400
