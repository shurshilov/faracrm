# Fara CRM — Test Suite

## Структура

```
backend/tests/
├── conftest.py                    # Главная конфигурация: БД, фикстуры, фабрики
├── pytest.ini                     # Конфигурация pytest
├── unit/                          # Юнит тесты (без БД)
│   ├── test_utils.py              # Валидация паролей, хеширование, схемы, поля моделей
│
├── integration/                   # Интеграционные тесты (с тестовой БД)
│   ├── users/
│   │   ├── test_user_model.py     # CRUD, пароли, сессии, роли, сериализация
│   │   └── test_user_api.py       # API: signin, password_change, copy, CRUD, авторизация
│   ├── security/
│   │   └── test_security.py       # Роли, ACL, правила, сессии, модели, приложения
│   ├── partners/
│   │   └── test_partners.py       # Партнёры, контакты, типы контактов, иерархия
│   ├── leads/
│   │   └── test_leads.py          # Лиды, стадии, типы, команды продаж
│   ├── sales/
│   │   └── test_sales.py          # Продажи, стадии, строки заказа, налоги
│   ├── products/
│   │   └── test_products.py       # Товары, категории, единицы измерения
│   ├── attachments/
│   │   └── test_attachments.py    # Файлы, хранение, полиморфные связи
│   ├── chat/
│   │   └── test_chat.py           # Чаты, сообщения, поиск, удаление
│   └── tasks/
│       └── test_tasks.py          # Проекты, задачи, стадии, теги
└── fixtures/                      # (зарезервировано для тестовых данных)
```

## Быстрый старт

### 1. Установить зависимости

```bash
pip install pytest pytest-asyncio pytest-cov httpx
```

### 2. Настроить переменные окружения (опционально)

```bash
export TEST_DB_NAME=fara_crm_test
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_USER=openpg
export DB_PASSWORD=openpgpwd
```

По умолчанию используются значения выше.

### 3. Запуск тестов

```bash
# Все тесты
cd backend
pytest tests/ -v

# Только юнит тесты (не нужна БД)
pytest tests/unit/ -v -m unit

# Только интеграционные тесты
pytest tests/integration/ -v -m integration

# Конкретный модуль
pytest tests/integration/users/ -v
pytest tests/integration/sales/ -v

# С покрытием кода
pytest --cov=backend --cov-report=html --cov-report=term-missing

# Только быстрые тесты
pytest -m "not slow"
```

## Как работает тестовая БД

1. **Автоматическое создание**: при старте тестов создаётся БД `fara_crm_test`
2. **Создание таблиц**: все таблицы создаются один раз за сессию
3. **Очистка**: `clean_tables` фикстура делает TRUNCATE CASCADE перед каждым тестом
4. **Удаление**: после завершения всех тестов БД удаляется

## Фабрики

Доступны готовые фабрики для создания тестовых данных:

```python
async def test_example(user_factory, partner_factory, product_factory):
    user = await user_factory(name="John", login="john", is_admin=True)
    partner = await partner_factory(name="Acme Corp")
    product = await product_factory(name="Widget", price=99.99)
```

Фабрики автоматически создают зависимые объекты (например, `user_factory` создаёт язык).

## Маркеры

| Маркер         | Описание                          |
|----------------|-----------------------------------|
| `unit`         | Не требует БД                     |
| `integration`  | Требует PostgreSQL                |
| `api`          | Тест API endpoint                 |
| `slow`         | Медленный тест                    |

## Статистика тестов

| Модуль       | Unit | Integration | API  | Итого |
|--------------|------|-------------|------|-------|
| Users        | 30   | 25          | 15   | 70    |
| Security     | —    | 20          | —    | 20    |
| Partners     | —    | 18          | —    | 18    |
| Leads        | —    | 16          | —    | 16    |
| Sales        | —    | 14          | —    | 14    |
| Products     | —    | 12          | —    | 12    |
| Attachments  | —    | 12          | —    | 12    |
| Tasks        | —    | 10          | —    | 10    |
| Chat         | —    | 8           | —    | 8     |
| **Итого**    | **30** | **135**   | **15** | **~180** |

## Добавление новых тестов

1. Создать файл `test_<name>.py` в соответствующей папке
2. Добавить маркер `pytestmark = pytest.mark.integration`
3. Использовать фикстуры `db_pool`, `clean_tables`, фабрики
4. Следовать паттерну: один класс на группу тестов (Create/Read/Update/Delete)
