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
        options=[
            ("open", "Открыт"),
            ("in_progress", "В работе"),
            ("resolved", "Решён"),
            ("closed", "Закрыт"),
        ],
        default="open",
    )
    priority: str = Selection(
        options=[
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

## Шаг 6: Frontend — List и Form

Стандартный подход — использовать готовые компоненты `<List>` и `<Form>` FARA. Они сами берут поля из бэкенда (имена, типы, валидацию), сами рисуют таблицу/форму, сами вызывают CRUD API.

### List

```tsx title="frontend/src/fara_tickets/List.tsx"
import type { TicketRecord } from '@/types/records';
import { Badge } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

export function ViewListTickets() {
  const { t } = useTranslation('tickets');

  return (
    <List<TicketRecord> model="tickets" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="title" label={t('fields.title')} />
      <Field
        name="status"
        label={t('fields.status')}
        render={value => {
          const colors: Record<string, string> = {
            open: 'blue',
            in_progress: 'yellow',
            resolved: 'green',
            closed: 'gray',
          };
          return (
            <Badge size="sm" variant="light" color={colors[value]}>
              {value}
            </Badge>
          );
        }}
      />
      <Field name="priority" label={t('fields.priority')} />
      <Field name="assigned_to" label={t('fields.assigned_to')} />
    </List>
  );
}
```

`<List model="...">` сам делает запрос к `/api/crud-auto/tickets/search`, рисует пагинацию, сортировку, фильтры, чекбоксы для bulk-операций. Тебе остаётся только перечислить поля и опционально дать им свой `render`.

### Form

```tsx title="frontend/src/fara_tickets/Form.tsx"
import type { TicketRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormRow, FormSection } from '@/components/Form/Layout';

export function ViewFormTickets(props: ViewFormProps) {
  const { t } = useTranslation('tickets');

  return (
    <Form<TicketRecord> model="tickets" {...props}>
      <FormSection title={t('sections.main')}>
        <FormRow cols={2}>
          <Field name="title" />
          <Field name="status" />
        </FormRow>
        <Field name="description" />
        <FormRow cols={2}>
          <Field name="priority" />
          <Field name="assigned_to" />
        </FormRow>
      </FormSection>
    </Form>
  );
}
```

`<Form model="...">` сам:

- На открытии — делает GET к API и подставляет значения.
- На submit — POST для создания, PATCH для обновления.
- Валидирует обязательные поля по схеме с бэкенда.
- Показывает toast об успехе/ошибке.

Для большинства CRM-моделей этого достаточно — модуль работает без единой строчки императивного кода.

### Кастомный список <span class="tag tag-internal">advanced</span>

Если стандартного `<List>` мало (нестандартный layout, kanban, диаграмма Ганта, гриппировки) — пишется кастомный компонент через `crudApi` напрямую. Пример:

```tsx title="frontend/src/fara_tickets/CustomKanban.tsx — для нестандартных случаев"
import { crudApi } from '@services/api/crudApi';

function TicketKanban() {
    const { data, isLoading } = crudApi.useSearchQuery({
        model: 'tickets',
        filter: [['is_archived', '=', false]],
        fields: ['id', 'title', 'status', 'priority'],
        order: 'id',
        sort: 'desc',
        limit: 50,
    });

    // Свой layout — группировка по статусам, drag-and-drop карточек и т.п.
    return <YourCustomLayout tickets={data?.data ?? []} loading={isLoading} />;
}
```

Это путь для случаев, когда таблица или форма принципиально не подходят. Подавляющее большинство модулей использует `<List>` + `<Form>` без кастомизации.

## Чеклист

- [x] Модель в `models/`
- [x] Service в `app.py`
- [x] Регистрация в `project_setup.py` (Models + Apps.installed)
- [x] Кастомные роутеры (если нужны)
- [x] Frontend API service
- [x] Frontend компоненты
- [ ] Локализация (`locales/ru.json`, `locales/en.json`)
- [ ] Тесты
