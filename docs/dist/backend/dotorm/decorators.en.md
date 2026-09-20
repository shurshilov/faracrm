# Decorators

Three decorators cover three moments in a record's life: the form reacting to input, derived data after the write, and validation before the write.

| | `@onchange` | `@depends` | `@constrains` |
|---|---|---|---|
| Purpose | Fill form values in response to input | Stored fields computed from other fields | A constraint: let the write through or reject it |
| When | On field blur in the form, via `POST /onchange` | After INSERT/UPDATE/DELETE, bulk included | Before INSERT/UPDATE, bulk included |
| Caller | Frontend | CRUD | CRUD |
| What is in `self` | All form values | The record from the database plus prefetched relations | An empty model instance; the records come in `records` |
| Result | A `dict` of values for the form | Assigned fields are written by the engine in one UPDATE | Nothing; an exception cancels the operation |
| Can reject the write | No | No, the row is already written | Yes |
| Runs for API and webhooks | No | Yes | Yes |

The order inside `create` and `update` is the same, and so are the bulk paths:

```
model ACL → field ACL → defaults (create) → @constrains → INSERT / UPDATE → row rules (create) → @depends
```

Two rules follow from the order. `@constrains` does not see `@depends` values of the same record, they are computed afterwards. `@onchange` is a hint, not a guarantee: anything that must hold for the API, webhooks and imports lives in `@constrains` or `@depends`.

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

- `self` carries all form values, M2O fields arrive as objects.
- Return only what should change; an empty `dict` means "nothing".
- Several handlers of one field run in alphabetical order of their names and are merged with `dict.update`, so an extension whose name sorts after the base handler overrides its values.
- Handlers are collected into a cache when the class is created and again after `@extend`; the class is not scanned per request.
- `@depends` trigger fields are part of the onchange field list too: the form calls `/onchange` and receives recomputed computed fields.

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

- A field is bound to its method through `compute="..."`, the method assigns the value on `self`.
- `triggers` are the fields whose change causes a recompute; a path through O2M/M2M (`"line_ids.price_subtotal"`) recomputes the parent when a child changes.
- `prefetch` lists relations the engine loads onto `self` before calling the method.
- `@depends()` without triggers recomputes the whole table after any operation on it, meant for small reference tables only.
- The engine accumulates marks during an operation and flushes them once: one SELECT of missing records and one `UPDATE ... FROM unnest` per (model, method) pair.

## `@constrains`

In essence it is an easy way to add a constraint to all four write paths at once, `create`, `update`, `create_bulk` and `update_bulk`, with a single function and without overriding each of them. The check runs before the database query: if it fires, the INSERT or UPDATE is never sent, so there is nothing to roll back.

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
            if record.login in by_login:  # duplicate inside the batch
                raise FaraException({"content": "USER_LOGIN_EXISTS"})
            by_login[record.login] = record
        if not by_login:
            return
        existing = await self.sudo().search(
            filter=[("login", "in", list(by_login))], fields=["id", "login"]
        )
        for other in existing:
            if other.id != by_login[other.login].id:  # except itself
                raise FaraException({"content": "USER_LOGIN_EXISTS"})
```

- The decorator arguments are trigger fields, as strings or field objects. The check runs when at least one record writes one of them; with no arguments it runs on every write.
- One call per operation, like `@api.constrains` with a recordset in Odoo. `self` is an empty model instance, as with `hybridmethod` called on the class, so that `self.sudo().search(...)` works. `records` are the payloads being written: one record for `create` and `update`, all rows for bulk. On `create` the record `id` is empty, on `update` it is set.
- A rule batches its own queries: one `IN` over the values of all records instead of a query per row. Duplicates inside the batch are not in the database yet, they are caught in the same loop.
- On `update` the payload carries only the changed fields. A rule that needs the others reads them with one `search` by record ids into the unassigned payload attributes. They never reach SQL: `update` writes by its field list, `update_bulk` hands the rule copies.
- Works from `@extend` extensions: methods are collected into the model cache by marker, not by name, so extensions do not overwrite each other and need no `call_original`.
- A model without checks pays nothing: the calls sit behind a guard on the empty cache.
- A uniqueness check in Python stays racy; the only guarantee is `unique=True` in the database. The check gives a readable error, the index gives the guarantee.

## What the decorators do not cover

Normalising values before the write, side effects after the write and delete guards are done by overriding `create`, `update` and `delete`. Overrides must be repeated for the bulk paths.
