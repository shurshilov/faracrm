# Создание нового модуля

Пошаговый гайд: от модели до UI за 6 шагов.

!!! example "Пример"
    Создадим модуль **Tickets** — система тикетов поддержки.

## Шаг 1: Модель

```python title="backend/base/crm/tickets/models/ticket.py"
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.fields import (
    Char, Text, Boolean, Selection, Datetime, Many2one
)


class Ticket(DotModel):
    __table__ = "tickets"

    title: str = Char(max_length=255, required=True)
    descriptione: str = Text()
    statuse: str = Selection(
        selection=[
            ("open", "Открыт"),
            ("in_progress", "В работе"),
            ("resolved", "Решён"),
            ("closed", "Закрыт"),
        ],
        default="open",
    )
    priority: str = Selection(
        selection=[
            ("low", "Низкий"),
            ("medium", "Средний"),
            ("high", "Высокий"),
            ("critical", "Критический"),
        ],
        default="medium",
    )
    assigned_to: "User | None" = Many2one["User"](relation_table="users")
    created_by: "User" = Many2one["User"](relation_table="users", required=True)
    is_archived: bool = Boolean(default=False)
```

```python title="backend/base/crm/tickets/models/__init__.py"
from .ticket import Ticket
```

## Шаг 2: Service

```python title="backend/base/crm/tickets/app.py"
from backend.base.system.core.service import Service


class TicketsService(Service):
    info = {
        "name": "Tickets",
        "depends": ["security"],
    }

    async def startup(self, app):
        await super().startup(app)

    async def shutdown(self, app):
        pass
```

## Шаг 3: Регистрация

```python title="backend/project_setup.py"
class Models(ModelsCore):
    # ...существующие модели...
    ticket = Ticket  # (1)!


class Apps(AppsCore):
    # ...добавляем приложение/ сервис...
    # сервис чтобы он выполнялись стартап и шатдаун
    # апы для того чтобы понимать список и версии приложений
    # установленных в системе
    tickets = TicketsService() # (2)!
```

1. Имя `ticket` → доступ через `env.models.ticket`
2. Путь к модулю → Environment найдёт `app.py` и `routers/`

!!! success "Готово — CRUD API работает"
    После перезапуска сервера модель получает автоматические эндпоинты:

    - `POST /tickets/search`
    - `POST /tickets/create`
    - `GET /tickets/read/{id}`
    - `PATCH /tickets/update/{id}`
    - `DELETE /tickets/delete`

## Шаг 4: Кастомные роутеры (опционально)

Если нужна бизнес-логика помимо CRUD:

```python title="backend/base/crm/tickets/routers/tickets.py"
from fastapi import APIRouter, Request
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session
router_private = APIRouter(prefix="/tickets", tags=["Tickets"])


@router_private.post("/{ticket_id}/assign")
async def assign_ticket(req: Request, ticket_id: int, body: AssignBody):
    """Назначить тикет на сотрудника."""
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    ticket = await env.models.ticket.get(ticket_id)
    await ticket.update(env.models.ticket(
        assigned_to=body.user_id,
        status="in_progress",
    ))

    return {"success": True}


@router_private.post("/{ticket_id}/close")
async def close_ticket(req: Request, ticket_id: int):
    """Закрыть тикет."""
    env: "Environment" = req.app.state.env

    ticket = await env.models.ticket.get(ticket_id)
    await ticket.update(env.models.ticket(status="closed"))

    return {"success": True}
```

## Шаг 5: Frontend — API service

```typescript title="frontend/src/services/api/tickets.ts"
// Для базового CRUD используй crudApi:
import { crudApi } from './crudApi';

// Для кастомных эндпоинтов — отдельный API:
export const ticketApi = crudApi.injectEndpoints({
    endpoints: (build) => ({
        assignTicket: build.mutation<void, { ticketId: number; userId: number }>({
            query: ({ ticketId, userId }) => ({
                method: 'POST',
                url: `/tickets/${ticketId}/assign`,
                body: { user_id: userId },
            }),
            invalidatesTags: ['tickets'],
        }),

        closeTicket: build.mutation<void, { ticketId: number }>({
            query: ({ ticketId }) => ({
                method: 'POST',
                url: `/tickets/${ticketId}/close`,
            }),
            invalidatesTags: ['tickets'],
        }),
    }),
});

export const { useAssignTicketMutation, useCloseTicketMutation } = ticketApi;
```

## Шаг 6: Frontend — компонент

```tsx title="frontend/src/fara_tickets/components/TicketList.tsx"
import { crudApi } from '@services/api/crudApi';
import { DataTable } from 'mantine-datatable';

function TicketList() {
    const { data, isLoading } = crudApi.useSearchQuery({
        model: 'tickets',
        filter: [['is_archived', '=', false]],
        fields: ['id', 'title', 'status', 'priority', 'assigned_to'],
        order: 'id',
        sort: 'desc',
        limit: 50,
    });

    const statusColors: Record<string, string> = {
        open: 'blue',
        in_progress: 'yellow',
        resolved: 'green',
        closed: 'gray',
    };

    return (
        <DataTable
            records={data?.data ?? []}
            fetching={isLoading}
            columns={[
                { accessor: 'id', width: 80 },
                { accessor: 'title', title: 'Тема' },
                {
                    accessor: 'status',
                    title: 'Статус',
                    render: (r) => (
                        <Badge color={statusColors[r.status]}>
                            {r.status}
                        </Badge>
                    ),
                },
                { accessor: 'priority', title: 'Приоритет' },
            ]}
        />
    );
}
```

## Чеклист

- [x] Модель в `models/`
- [x] Service в `app.py`
- [x] Регистрация в `project_setup.py` (Models + Apps.installed)
- [ ] Кастомные роутеры (если нужны)
- [ ] Frontend API service
- [ ] Frontend компоненты
- [ ] Локализация (`locales/ru.json`, `locales/en.json`)
- [ ] Тесты
