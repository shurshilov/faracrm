# Юнит-тесты

Самый низкий уровень тестов. Проверяют **отдельные функции и классы в изоляции** — без БД, сети, диска, FastAPI. Запускаются за миллисекунды каждый.

## Когда писать

- Парсер/форматтер/конвертер — на разные форматы входа и edge cases.
- Validator — на корректные/некорректные значения.
- Helper-функция (`format_phone`, `truncate_text`, `parse_domain`) — на граничные случаи.
- Pure-логика без I/O — расчёт скидки, компоновка строки, SQL-фильтр-билдер.

## Когда **не** писать

- Если функция делает запрос в БД — это уже integration.
- Если функция вызывает другую функцию, которую ты тоже пишешь — может стоит протестировать обе вместе через integration, чтобы не моки писать.
- Если функция тривиальная (`def add(a, b): return a + b`) — тест не даёт ценности.

## Структура

```
tests/unit/
├── conftest.py              # фикстуры без БД
├── parsers/
│   ├── test_phone_parser.py
│   └── test_url_parser.py
├── validators/
│   └── test_email_validator.py
└── helpers/
    └── test_format_helpers.py
```

## Пример

```python title="tests/unit/parsers/test_phone_parser.py"
import pytest
from backend.base.crm.partners.utils.phone_parser import normalize_phone


class TestNormalizePhone:
    """Юнит-тесты — без БД, без сети."""

    def test_e164_format(self):
        assert normalize_phone("+7 (495) 123-45-67") == "+74951234567"

    def test_no_plus(self):
        assert normalize_phone("8 495 123 45 67") == "+74951234567"

    def test_with_country_code(self):
        assert normalize_phone("+1-555-123-4567") == "+15551234567"

    @pytest.mark.parametrize("invalid", [
        "",
        "abc",
        "12",       # слишком коротко
        "+",
        None,
    ])
    def test_invalid_returns_none(self, invalid):
        assert normalize_phone(invalid) is None
```

## Конвенции

- **Один файл = один модуль/функция**. `test_phone_parser.py` тестирует `phone_parser.py`.
- **Класс = группа сценариев одной функции**. `TestNormalizePhone` для `normalize_phone()`.
- **Метод = один сценарий**. `test_e164_format`, `test_no_plus` — каждый о своём.
- **Параметризация** через `@pytest.mark.parametrize` для одинаковой логики на разных входных.

## Запуск

```bash
pytest tests/unit/ -v

# Конкретный файл
pytest tests/unit/parsers/test_phone_parser.py -v

# Конкретный класс
pytest tests/unit/parsers/test_phone_parser.py::TestNormalizePhone -v

# С coverage
pytest tests/unit/ --cov=backend/base/crm/partners/utils -v
```

## Без БД — категорически

Если в юнит-тесте нужно сделать `await Model.search(...)` — это уже не юнит. Перенеси в `tests/integration/` либо отрефактори тестируемый код, чтобы DB-операцию можно было вынести в зависимость.

```python
# ❌ Это integration, не unit
async def test_search_users():
    users = await env.models.user.search(...)
    assert users

# ✓ Это unit
def test_user_filter_builder():
    filter = build_user_filter(role="admin", active=True)
    assert filter == [("role_id.name", "=", "admin"), ("active", "=", True)]
```

## Скорость

Юнит-тесты должны идти **за миллисекунды**. Если файл из 50 тестов идёт 5 секунд — что-то не так: либо они не юнит-тесты (есть I/O), либо в коде неоправданная инициализация. Проверка:

```bash
pytest tests/unit/ --durations=10
# Покажет 10 самых медленных. Если в топе — миллисекунды, всё хорошо.
```

## См. также

- [Интеграционные тесты](integration.md) — тесты с БД и API
- [Performance](performance.md) — про замеры скорости
