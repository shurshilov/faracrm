# Extensions without core changes

Customer-specific fields, sections and tabs are added to a model from a separate module; core files stay untouched. A core update (`git pull`, a new image) does not overwrite such code: it lives in a folder the core never changes and knows nothing about.

Backend and frontend work the same way:

| | Backend | Frontend |
|---|---|---|
| Folder | `backend/business/` | `frontend/src/business/` |
| What is picked up | `*_ext.py` and `extensions/` packages — `ExtensibleMixin._autodiscover` | `<module>/index.ts` or `index.tsx` — `import.meta.glob` in `useModelExtensions` |
| How it extends | `@extend(Model)`: fields, methods, `selection_add`; columns are created by auto-DDL | `registerExtension` and `registerFormTab`: form sections and tabs, kanban cards |
| When it loads | At server start | When a form or kanban opens, after the core modules |

## Module

```
frontend/src/business/
└── partner_client/            # any name; modules load in alphabetical order
    ├── index.ts               # entry point: side-effect imports only
    └── ViewFormPartner.tsx    # component + registerExtension(...)
```

- The build finds `index.ts` on its own; nothing goes into `config/models.ts`. Core modules from `modelsConfig[model].extensions` load first, then business modules one by one in alphabetical folder order, so the registration order is deterministic.
- `yarn build` type-checks `src/business` with the same `tsc`, Docker copies the whole `frontend/`: there are no extra build steps.
- In dev mode a new folder is picked up without restarting Vite.

## Positions

`registerExtension(model, Component, position, fields)`:

| Position | Where it renders |
|---|---|
| `before:FormTabs`, `after:FormTabs` | Above and below the tabs block |
| `after:FormSheet` | Below the main `FormSheet` block |
| `before:FormTab:<name>`, `after:FormTab:<name>` | At the start and at the end of the `<name>` tab content |
| `replace:FormTab:<name>` | Instead of the tab content; the last registered wins |
| `before:KanbanCard`, `after:KanbanCard`, `replace:KanbanCard` | Kanban card; the component receives `{ record, model }` |

A new tab is `registerFormTab(model, { name, label, icon, component }, fields)`; it goes after the tabs from the form markup. Tab names are the `<FormTab name="...">` of the form's `Form.tsx` (`fara_partners/Form.tsx` and so on).

Several extensions at one position render in registration order: core modules, then business modules in alphabetical folder order, and inside a module in call order.

## Example: customer fields on the partner card

Backend, `backend/business/partner_client_ext.py`:

```python
from datetime import date

from backend.base.crm.partners.models.partners import Partner
from backend.base.system.core.extensions import extend
from backend.base.system.dotorm.dotorm.fields import Char, Date, Selection


@extend(Partner)
class PartnerClient:
    client_code: str | None = Char(max_length=32, string="Client code")
    client_since: date | None = Date(string="Client since")
    segment: str | None = Selection(
        options=[("retail", "Retail"), ("b2b", "B2B")],
        string="Segment",
    )
```

Frontend, `frontend/src/business/partner_client/index.ts`:

```ts
import './ViewFormPartner';
```

`frontend/src/business/partner_client/ViewFormPartner.tsx`:

```tsx
import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FieldDate } from '@/components/Form/Fields/FieldDate';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { registerExtension } from '@/shared/extensions';

export function PartnerClientSection() {
  return (
    <FormSection title="Client">
      <FormRow cols={3}>
        <FieldChar name="client_code" label="Client code" />
        <FieldDate name="client_since" label="Client since" />
        <FieldSelection name="segment" label="Segment" />
      </FormRow>
    </FormSection>
  );
}

registerExtension('partners', PartnerClientSection, 'before:FormTabs', [
  'client_code',
  'client_since',
  'segment',
]);
```

Three rules:

- The `fields` list is mandatory: the form merges it with the markup fields in the record request and in `default_values`. Without it the fields arrive with neither data nor metadata and do not render.
- Inside an extension use the concrete field components (`FieldChar`, `FieldMany2one`, … from `components/Form/Fields`), not `<Field>`: dispatch by server type works only for children of `<Form>`. Required flags, `Selection` options and the related model come from the form context.
- Neighbouring values are read with `useFormContext().getValues()`. The record type with the new fields is declared in the module (`interface PartnerClientRecord extends PartnerRecord`); `types/records.ts` needs no edit.

## What cannot be extended this way

A new model, menu item or route goes through `config/models.ts`; lists (`<List>`) have no extension points.
