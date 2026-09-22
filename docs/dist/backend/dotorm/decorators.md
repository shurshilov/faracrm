# Декораторы

Три декоратора закрывают три момента жизни записи: реакцию формы на ввод, производные данные после записи и проверку перед записью.

| | `@onchange` | `@depends` | `@constrains` |
|---|---|---|---|
| Назначение | Подставить значения в форму в ответ на ввод | Хранимые поля, вычисляемые из других | Ограничение: пропустить запись или отклонить |
| Когда | На blur поля в форме, через `POST /onchange` | После INSERT/UPDATE/DELETE, включая bulk | До INSERT/UPDATE, включая bulk |
| Кто вызывает | Фронт | CRUD | CRUD |
| Что в `self` | Все значения формы | Запись из базы плюс prefetch связей | Пустой экземпляр модели; записи приходят в `records` |
| Результат | `dict` значений для формы | Присвоенные поля пишет движок одним UPDATE | Ничего; исключение отменяет операцию |
| Может отклонить запись | Нет | Нет, строка уже записана | Да |
| Работает через API и вебхуки | Нет | Да | Да |

Порядок внутри `create` и `update` одинаковый, bulk-пути те же:

```
ACL модели → ACL полей → defaults (create) → @constrains → INSERT / UPDATE → row rules (create) → @depends
```

Из порядка следуют два правила. `@constrains` не видит значения `@depends` той же записи, они считаются после. `@onchange` это подсказка, а не гарантия: всё, что должно выполняться через API, вебхуки и импорт, живёт в `@constrains` или `@depends`.

## `@onchange`

```python
from backend.base.system.dotorm.dotorm.decorators import onchange

class ChatConnector(DotModel):

    @onchange("type")
    async def _onchange_type(self) -> dict:
        if self.type == "telegram":
            return {"connector_url": "https://api.telegram.org"}
        return {}
```

- `self` заполнен всеми значениями формы, M2O приходят объектами.
- Возвращает только то, что надо изменить; пустой `dict` означает «ничего».
- Несколько обработчиков одного поля идут по алфавиту имён и мержатся `dict.update`, поэтому расширение с именем «после» базового перекрывает его значения.
- Обработчики собираются в кэш при создании класса и после `@extend`, на каждый запрос класс не обходится.
- Поля-триггеры `@depends` тоже попадают в список onchange-полей: форма дёргает `/onchange` и получает пересчитанные вычисляемые поля.

## `@depends`

```python
from backend.base.system.dotorm.dotorm.decorators import depends

class SaleLine(DotModel):
    price_unit: float = Float()
    qty: float = Float()
    price_subtotal: float = Float(compute="_compute_subtotal")

    @depends(triggers=[price_unit, qty])
    async def _compute_subtotal(self) -> None:
        self.price_subtotal = self.price_unit * self.qty
```

- Поле связывается с методом через `compute="..."`, метод присваивает значение на `self`.
- `triggers` — поля, при изменении которых идёт пересчёт; путь через O2M/M2M (`"line_ids.price_subtotal"`) пересчитывает родителя при изменении ребёнка.
- `prefetch` — связи, которые движок догружает на `self` до вызова метода.
- `@depends()` без триггеров пересчитывает всю таблицу после любой операции над ней, только для маленьких справочников.
- Движок копит пометки за операцию и сливает их один раз: один SELECT недостающих записей и один `UPDATE ... FROM unnest` на пару (модель, метод).

## `@constrains`

По сути это лёгкий способ добавить ограничение сразу во все четыре пути записи, `create`, `update`, `create_bulk` и `update_bulk`, одной функцией, без override'ов каждого из них. Проверка выполняется до запроса к базе: сработала, значит INSERT или UPDATE не отправляется, откатывать нечего.

```python
from backend.base.system.dotorm.dotorm.decorators import constrains

class User(DotModel):
    login: str = Char(max_length=50, unique=True)

    @constrains("login")
    async def _constrains_login_unique(self, records: list[Self]) -> None:
        by_login = {}
        for record in records:
            if not record.login:
                continue
            if record.login in by_login:  # дубль внутри пачки
                raise FaraException({"content": "USER_LOGIN_EXISTS"})
            by_login[record.login] = record
        if not by_login:
            return
        existing = await self.sudo().search(
            filter=[("login", "in", list(by_login))], fields=["id", "login"]
        )
        for other in existing:
            if other.id != by_login[other.login].id:  # кроме себя
                raise FaraException({"content": "USER_LOGIN_EXISTS"})
```

- Аргументы декоратора — поля-триггеры, строки или объекты полей. Проверка идёт, когда среди записываемых полей хотя бы одной записи есть одно из них; без аргументов — при любой записи.
- Вызов один на операцию. `self` — пустой экземпляр модели, как у `hybridmethod` при вызове от класса, для `self.sudo().search(...)`. `records` — записываемые payload'ы: одна запись у `create` и `update`, все строки у bulk. На `create` у записи `id` пустой, на `update` выставлен.
- Правило батчит запросы само: одно `IN` по значениям всех записей вместо запроса на строку. Дубли внутри самой пачки в базе ещё не видны, их ловят в том же цикле.
- На `update` payload несёт только изменяемые поля. Если правилу нужны остальные, оно читает их одним `search` по `id` записей в незаданные атрибуты payload. В SQL это не попадёт: `update` пишет по списку полей, `update_bulk` отдаёт правилу копии.
- Работает из `@extend`-расширений: методы собираются в кэш модели по маркеру, а не по имени, расширения не затирают друг друга и не требуют `call_original`.
- У модели без проверок стоимость нулевая: вызовы стоят под гардом пустого кэша.
- Python-проверка уникальности остаётся гоночной, единственная гарантия это `unique=True` в базе. Проверка нужна для понятной ошибки, индекс для гарантии.

## Что не покрыто декораторами

Нормализация значений до записи, побочные эффекты после записи и защита удаления делаются override'ами `create`, `update` и `delete`. Override нужно повторять для bulk-путей.
