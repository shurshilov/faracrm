# Тесты производительности

Замеры скорости и потребления ресурсов под нагрузкой. **Не проверяют корректность данных** — только то, что система отрабатывает за разумное время.

## Когда писать

- Переписал хот-метод (`Model.search`, `serialize_*`, рендер сообщений).
- Добавил новый indexed-запрос — проверить, что план запроса не съехал.
- Реализовал bulk-операцию (`update_bulk`, `create_bulk`) — измерить throughput.
- Регрессия в production — нужно зафиксировать baseline и потом проверить, что фикс реально вернул скорость.

## Когда **не** писать

- Общий бенчмарк «насколько быстра FARA» — это маркетинговая задача, не инженерная.
- Микрооптимизации, которые не на горячем пути — потеря времени.
- Тестирование без зафиксированной baseline — без сравнения числа ничего не значат.

## Структура

```
tests/performance/
├── conftest.py                    # фикстуры: bigdata, profiler
├── test_orm_performance.py        # search, create, update под нагрузкой
├── test_serialization.py          # сериализация Many2one/One2many
└── test_websocket_throughput.py   # сколько сообщений/сек выдержит WS
```

## Пример: ORM-бенчмарк

```python title="tests/performance/test_orm_performance.py"
import time
import pytest
from backend.base.crm.partners.models.partner import Partner


@pytest.mark.performance
class TestORMPerformance:
    """Бенчмарки DotORM. Базовая планка — search 10000 записей < 200ms."""

    @pytest.fixture(autouse=True)
    async def setup(self, env, big_dataset):
        """big_dataset фикстура заранее заливает 10k партнёров."""
        self.env = env

    async def test_search_10k_indexed(self, env, performance_baseline):
        """Поиск по индексированному полю по 10k записей."""
        start = time.perf_counter()
        partners = await Partner.search(
            filter=[("type", "=", "company")],
            fields=["id", "name"],
            limit=100,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(partners) == 100
        # Регрессия: было 50ms, стало 300ms — упадёт CI
        assert elapsed_ms < performance_baseline.get(
            "search_10k_indexed", 200
        )

    async def test_bulk_create_1000(self, env, performance_baseline):
        """Создание 1000 записей через bulk."""
        records = [Partner(name=f"P{i}", type="person") for i in range(1000)]

        start = time.perf_counter()
        await Partner.create_bulk(records)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < performance_baseline.get(
            "bulk_create_1000", 1500
        )
```

## Baseline и регрессии

Производительность сама по себе не говорит ничего: `200ms` — это много или мало? Имеет смысл сравнение **с предыдущим значением**.

Способ — **зафиксированные baselines**:

```python title="tests/performance/baselines.json"
{
    "search_10k_indexed": 200,
    "bulk_create_1000": 1500,
    "serialize_many2one_chain": 50,
    "ws_messages_per_second": 1000
}
```

Тесты сравнивают с этими числами + дают ~30% буфер. Если код стал в 2 раза медленнее — CI падает. Если стал в 2 раза быстрее — обновляешь baseline руками.

## pytest-benchmark — для микро-замеров

Для ручной микро-оптимизации удобен пакет `pytest-benchmark`:

```python
def test_filter_builder(benchmark):
    result = benchmark(build_filter, role="admin", active=True)
    assert result == [...]
```

```bash
pytest tests/performance/test_filter_builder.py --benchmark-only
```

Покажет min/max/mean/stddev — статистику по 100+ повторов. Полезно когда хочешь сравнить две реализации.

## Нагрузочные тесты — Locust или k6

Для проверки «что будет при 100 одновременных юзерах» бенчмарки в pytest не подходят. Здесь — внешние инструменты:

```python title="tests/performance/locustfile.py"
from locust import HttpUser, task, between


class FaraUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.client.post("/api/auth/login", json={
            "login": "admin", "password": "admin",
        })

    @task(3)
    def list_leads(self):
        self.client.get("/api/crud-auto/leads/search?limit=50")

    @task(1)
    def create_lead(self):
        self.client.post("/api/crud-auto/leads/create", json={
            "name": "Test Lead",
            "manager_id": 1,
        })
```

Запуск:

```bash
locust -f tests/performance/locustfile.py --host=https://staging.fara.dev
# UI на http://localhost:8089 — задавай RPS, число юзеров, смотри график
```

## Что мерить

Для backend:

| Метрика | Что показывает | Целевая планка |
|---------|---------------|----------------|
| **p95 latency endpoint'а** | 95% запросов укладываются в Х | < 200ms для CRUD |
| **Search по 100k записей** | Регрессия плана запроса | < 500ms |
| **WS-broadcast 100 клиентам** | Узкое место в чате | < 50ms |
| **Cold start API** | Сколько FastAPI стартует | < 5s |
| **Memory per request** | Утечки | стабильно за 1000 запросов |

## CI

Performance-тесты обычно **не на каждый PR** — слишком долго и шумно. Запуск:

- **Раз в сутки** ночной prol всех бенчмарков с обновлением baseline.json.
- **На критичные PR** (помечены лейблом `perf-affecting`) — точечно.
- **Перед релизом** — обязательно полный прогон.

Результаты архивируются — построение графика регрессий по неделям/месяцам ценнее одного прогона.

## См. также

- [Интеграционные тесты](integration.md) — для проверки корректности
- [pytest-benchmark](https://pytest-benchmark.readthedocs.io/) — для микро-замеров
- [Locust](https://locust.io/) — для нагрузочного
