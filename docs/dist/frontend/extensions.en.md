# Extensions without core changes

Customer-specific fields, sections and tabs are added to a model from a separate module; core files stay untouched. A core update (`git pull`, a new image) does not overwrite such code: it lives in a folder the core never changes and knows nothing about.

Backend and frontend work the same way:

| | Backend | Frontend |
|---|---|---|
| Folder | `backend/business/` | `frontend/src/business/` |
| What is picked up | `*_ext.py` and `extensions/` packages — `ExtensibleMixin._autodiscover` | `<module>/index.ts` or `index.tsx` — `import.meta.glob` in `useModelExtensions`; core modules also `fara_<module>/extensions.ts` |
| How it extends | `@extend(Model)`: fields, methods, `selection_add`; columns are created by auto-DDL | `registerExtension` and `registerFormTab`: form sections and tabs, kanban cards; `registerPrintProvider`: items of the "Print" button |
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
| `provide:FormFields` | A form fields provider: a component without markup, rendered before the record loads, receives `{ model, layoutFields, onReport }` and reports `onReport({ ready, fields, required })` — which fields to add to the record request (they are not in the markup) and which to make required. The form loads the record once every provider is `ready` (`components/Form/formFieldProviders.tsx`) |
| `wrap:Form` | A wrapper around the form markup (inside `<form>`): the component receives `{ children, layoutFields }`, must render `children` and may place its own content around — below, on the side or as a tab via `FormTabsExtraContext` from `Form/Layout/FormTabs` (tabs added on the fly go last). Mounted while the form is open, even when the added content sits in a tab (Mantine hides an inactive tab via `Activity`). The first registered is the outermost |

The `'*'` model is an extension for all models at once. This is how the studio adds the "More" zone to every form: `registerExtension('*', StudioFormFields, 'provide:FormFields')` — the zone fields into the request, `registerExtension('*', StudioFormShell, 'wrap:Form')` — the zone itself around the markup. An icon in the application header is `registerHeaderAction(key, Component)` from `shared/extensions/headerActions`: the component decides itself whether to show. A full-height right panel under the header is `<LayoutAside width={…}>` from `shared/extensions/layoutAside`: while it is mounted the main area narrows by the panel width, and its children render into the panel through a portal (React contexts are kept); this is how the studio panel opens.

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

## For all models at once: the "Print" button

The "Print" button in the form toolbar belongs to the core (`components/Form/PrintButton.tsx`); what to print is supplied by modules through `registerPrintProvider(key, Provider)` from `@/shared/extensions/print`. A provider is an invisible component with props `{ model, recordId, onItems }`: it runs its own queries and permission checks and hands over items `{ key, label, icon?, group?, onSelect }` via `onItems` (keep the array reference stable with `useMemo`). While no provider has handed over anything, the form has no button; a single item runs on click, several items open a menu, and `group` adds a group heading. Example: `fara_report_docx/PrintProvider.tsx` — the record's DOCX templates and, for an administrator, the "Configure template" items.

A registration shared by all models lives in `extensions.ts` at the root of a core module (`fara_report_docx/extensions.ts`) or in the `index.ts` of a business module: `useModelExtensions` loads them together with the model's extensions.

## What cannot be extended this way

A new model, menu item or route goes through `config/models.ts`; lists (`<List>`) have no extension points.
