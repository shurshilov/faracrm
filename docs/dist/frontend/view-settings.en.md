# View settings without code

What can be changed in a list and on a form from the UI without touching the view markup. The settings live in the database (the `view_settings` module), so a code update does not overwrite them.

Every user configures the list and the kanban for themselves through the "⋮" menu on the right of the view header. The form is configured by the settings administrator in studio mode — the icon in the header, see [Studio](../backend/modules/studio.md).

| | List columns, kanban card fields | Form fields |
|---|---|---|
| Where | "⋮ → Columns" in the list, "⋮ → Card fields" in the kanban | studio mode (the header icon on a form) |
| Who | every user, for themselves | the settings administrator (superuser or the `system_admin` role), for everyone |
| Model | `column_settings` — a row per user, model and view (`view_type`: list, kanban) | `form_settings` — one row per model |
| Repair screen | Other → Column Settings | Other → Form Settings |

## List columns and card fields

A checkbox shows the field, arrows set the order, "Default" restores the view's fields. For relation columns (One2many, Many2many) in the list the gear sets the widget (count, "yes/no", text) and a filter on the related records, using the same condition editor as the list filter. Kanban card values render like list cells: a checkbox, a date, the record name for a relation, the record count for a relation list.

## Form fields

The shared form settings (`form_settings`) are the **required** fields and the **"More"** zone: fields missing from the markup, where the zone sits and its grid. They are edited in studio mode; changes are saved to the server after every action.

- **Zone placement** (`extra_placement`): below the markup, as a column on the right (collapsible with an arrow; below the markup on a narrow form) or as the last "More" tab of the form's `FormTabs`. On a form without tabs "tab" stays below the markup.
- **Grid** (`extra_columns` × `extra_rows`): a plain CSS grid, 1 column and any number of rows by default — like the former field list. Rows can be limited to a number.
- **Zone fields** (`extra_fields`) are cells `{"name", "x", "y", "w", "h"}`: the column and row of the top-left corner and the field size in cells. In studio mode a field is dropped into an empty cell (from the panel or from the zone itself); dropping onto another field swaps them if it fits into the former place. The size is set in the field's properties. The cross removes a field from the form. A field without a place (or one that no longer fits after the grid shrinks) takes the first free cell; its saved place is kept — restore the columns and the field returns. On a narrow screen zone fields go in one column, row by row.
- **Requirement** — in the selected field's properties and on the "Form fields" tab for markup fields. A required field outside the markup is shown in "More" by the form itself.

The requirement is UI-level, like Required on a field in Odoo Studio: the form shows an asterisk and refuses to save an empty value, while the `/auto` API and code (incoming messages, Excel import, cron) do not check it — otherwise auto-creating a partner from an incoming message without a tax ID would fail.

Table fields (One2many, Many2many) cannot be configured: without column markup the form cannot render them, and the backend rejects such names (`FORM_SETTING_UNKNOWN_FIELD`). The label of an extra field is the module translation `<model>:fields.<name>`, otherwise the field's `string` from the model, otherwise the technical name.

Code — the studio module `fara_studio`: the `zone/` folder — `ExtraFieldsDefault.tsx` (zone fields outside studio mode), `zoneGrid.ts` (cell placement, swapping, checks), `ExtraGrid.tsx` (the grid), `ZoneLayout.tsx` (where the zone sits; the tab goes through the core's `FormTabsExtraContext`), `ExtraZoneFrame.tsx` (the frame per placement); `useFormSettings.ts` (settings cache, warmed on startup; not loaded without the studio installed), `StudioFormFields.tsx` (zone fields into the record request — `provide:FormFields`), `StudioExtraFields.tsx` (the zone around the markup — via `wrap:Form`); backend — the studio model `studio/models/form_setting.py`; the editor — the `fara_studio` module.
