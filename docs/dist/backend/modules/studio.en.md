# Studio: model fields from the UI

The settings administrator adds a custom field to a model without code — in studio mode on the model's form. The field becomes a regular table column and a regular model field: the list, the form, filters, Excel export and the `/auto` API all see it.

## Installation

The studio is off by default: the administrator installs it on **Settings → Other → Apps** (`/apps`), without a restart. It is a removable service (`"core": False`): installing runs its `startup` — fields are attached to the models, auto-CRUD schemas and routes are rebuilt; uninstalling calls `shutdown` — fields are detached from the models, `/studio/*` routes are cut out. Columns, `studio_fields` rows and form settings stay in the database: reinstalling brings everything back. While the studio is not installed, the frontend neither loads nor applies form settings (no "More" zone and no requirement from the settings).

## Studio mode

The header icon (like Studio in Odoo) appears when a model form is open, the module is installed and the user is the settings administrator. In studio mode the form's "More" zone becomes a grid editor and a panel opens on the right under the header — the form narrows by its width, so the panel covers neither the markup, nor the "side" zone, nor the header.

Above the zone grid are its placement (below / side / tab) and the grid size (columns × rows, empty rows — as many as needed). Empty cells show as dashed outlines; the cell under the cursor turns violet if it accepts the field and red if not. Details — the "Form fields" section of [View settings](../../frontend/view-settings.md).

- **Add** — new fields by type and existing model fields; drag them into a zone cell, move zone fields by dragging too (onto another field — they swap), the cross removes a field from the form. A new field is created immediately: name `x_<type>_<number>`, label "New field"; "Link to record" asks for the model first.
- **Properties** — the selected field: label and options (for studio fields), technical name, type, width and height in cells, "Required", "Remove from form", "Delete field".
- **Form fields** — the requirement of markup fields; the studio does not touch the markup itself. A field required by the model is always on.

Every action is saved immediately. The frontend is the `fara_studio` module, plugged into the core with hooks: `registerHeaderAction` (the icon and warming up the form settings), `registerExtension('*', …, 'provide:FormFields')` (the "More" zone fields into the record request and required fields) and `registerExtension('*', …, 'wrap:Form')` (a wrapper around every form's markup: places the zone below, on the side or as a tab, tells the header a form is open, and in studio mode holds the editor, drag and drop and the panel). The zone, the grid and the form settings live in `fara_studio` (`zone/`, `useFormSettings.ts`, `formSettingsApi.ts`); the core knows nothing about them. The editor lives in the wrapper, not in the zone: Mantine hides a zone placed in a tab via `Activity`, and the icon and the panel would vanish along with its effects. Without the module the core behaves as before.

## How it works

- **Form settings** — the `form_settings` table (`models/form_setting.py`) also belongs to the studio: required fields and the "More" zone (placement, grid, cells). Everyone reads it, `system_admin` changes it; the access rows are created when the studio is installed.
- **Definition** — the `studio_fields` table (module `backend/base/system/studio`): model, technical name, label, type, selection options, related model. The database is the source of truth: a database dump carries the customization.
- **Startup.** The installed `studio` service starts after the install flags are read and before auto-CRUD (`sequence` 5): it attaches the fields to the models (`DotModel.add_fields` plus a type annotation for the API schemas) and adds missing columns with the regular DDL sync. Schemas and `/auto` routes are built with them.
- **Immediately, no restart.** `POST /studio/fields`: the row, the field on the model, `ALTER TABLE … ADD COLUMN`, the field in the "More" section of the shared form settings, a rebuild of schemas and auto routes in this worker (about 2 s), and a `studio_changed` event on the bus — other workers and cron bring their models up to date (`StudioApp.sync`; the studio subscribes to the event itself in `startup` via `env.apps.bus.subscribe`).
- **Editing.** `PATCH /studio/fields/{id}` — label and selection options; applied in place without rebuilding schemas, other workers get the same event.
- **Deletion.** `DELETE /studio/fields/{id}`: the row, the field off the model, the name removed from form settings. The column and its data stay in the database: a field created again with the same name and type gets the old values back. Dropping the column is disabled on purpose (commented out in the router and the database service).

## Rules

- Name: `x_` plus Latin letters, digits and underscore (`x_segment`). The prefix tells studio fields from core fields and keeps them from clashing.
- Type and name are immutable after creation — create the field again. Since the column survives deletion, a new field with an old name must have the same type.
- Types: text line, text, integer, number, checkbox, date, date and time, selection (value/label pairs), link to record (a model from the registry). Many2many, files and related fields — no.
- The label is the field's `string`; the form and the columns menu show it wherever the field has no label in the markup.

## Code

`models/studio_field.py` — the model and checks (`STUDIO_FIELD_*`), `build()` assembles the dotorm field; `app.py` — `refresh` (fields to match the table, label and options in place), `rebuild` (schemas and routes via `DotormCrudAutoService.rebuild`), `sync`, `publish`, `show_on_form`, `forget`; `routers/studio.py` — four endpoints. Core: `DotModel.remove_fields`, `DotormDatabasesPostgresService.sync_tables`. Frontend: `fara_studio` — `StudioToggle` (the icon), `StudioFormShell` (form wrapper, DndContext, panel), `StudioZone` (grid editor), `StudioPanel`, `useStudioEditor` (draft and saving the settings), `api.ts`.
