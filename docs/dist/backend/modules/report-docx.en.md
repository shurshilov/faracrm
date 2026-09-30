# DOCX reports and scheduled sending

The `report_docx` module is the engine: it builds documents (invoices, contracts, summary reports) from DOCX templates with Jinja2 tags, returns the result as DOCX or PDF and can deliver the file on a schedule — by email or to Telegram. Data functions and sample templates live in domain modules: for sales that is `sales_report_docx`. The in-browser template designer is a separate module, `report_docx_design`.

## Template anatomy

A template is a `report_template` record (menu "Report templates"):

<div class="field" markdown>
`python_function` <span class="field-type">Char</span>

Name of the data function: a `@staticmethod` `async def name(env, **params) -> dict`. It builds the **data dict** whose keys are the template tags. Where the data comes from is up to the function: one record (`params = {"record_id": id}`), a selection for a period, several models. An `images` list (bytes or base64) replaces pictures `1.jpg`, `2.jpg`… in the template — that is how stamps and signatures get in.
</div>

<div class="field" markdown>
`model_name` <span class="field-type">Char</span>

The model that holds the data function, by table name as in `/auto/{model}`: `sales`, `partners`. For a per-record document its form shows a "Print" button (`PrintButton` component) when at least one active template of that type exists.
</div>

<div class="field" markdown>
`report_type` <span class="field-type">record | summary</span>

`record` — per-record document: the function receives `record_id`, the template is listed in the "Print" menu. `summary` — summary report: there is no record, the function parameters come from a cron job or the route, and the template is hidden from the "Print" menu.
</div>

<div class="field" markdown>
`template_file` <span class="field-type">Attachment</span>

The DOCX file with `{{ tag }}`, `{% for %}`, `{% if %}` and, inside tables, `{%tr for %}` tags (docxtpl engine). Samples live in `backend/base/crm/sales_report_docx/templates/` (invoice, contracts, sales for a period) and are seeded as template records on startup, see [Default templates](#default-templates).
</div>

<div class="field" markdown>
`output_format` <span class="field-type">docx | pdf</span>

Default format; the route accepts `?output_format=` to override it.
</div>

Sales data functions are collected in `sales_report_docx/models/sale_ext.py` (`@extend(Sale)`), two kinds:

```python title="per-record document — report_type = record"
@staticmethod
async def sale_invoice_rus(env: "Environment", record_id: int) -> dict:
    sale = await env.models.sale.search_one(filter=[("id", "=", record_id)], ...)
    return {"so_number": sale.name, "customer": ..., "order_line": [...]}
```

```python title="summary report — report_type = summary"
@staticmethod
async def sales_period_data(env: "Environment", days: int = 30) -> dict:
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    sales = await env.models.sale.search(filter=[("date_order", ">=", date_from)], ...)
    return {
        "date_from": ..., "date_to": ..., "count": len(sales), "total": ...,
        "rows": [{"name": s.name, "partner": ..., "user": ..., "amount": ...} for s in sales],
        "by_user": [...],
    }
```

`sales_period_data` is a working example, "sales for the last N days" with totals per salesperson; its template is `sales_report_docx/templates/Отчёт по продажам за период.docx`. Your own report is a function like it in your module (or in `backend/business`): any queries, any keys, and a DOCX with tags matching those keys.

Generation goes through `ReportTemplate.render_attachment(template_id, params=None, output_format=None)`: it calls `python_function(env, **params)` and returns an unsaved `Attachment` (name, mimetype, content). The route and the scheduled sending both use it:

| Route | What it does |
|-------|--------------|
| `GET /reports/generate/{template_id}/{record_id}` | Per-record document: `params = {"record_id": record_id}` (the "Print" button) |
| `GET /reports/generate/{template_id}?params={"days":30}` | Summary report: data function parameters as a JSON object |

For a per-record document the context holds, besides the function dict, **all record fields** (`ReportTemplate.record_context`): scalars as they are, Many2one one level deep (`{{ partner_id.name }}`), One2many/Many2many lists as rows (`{%tr for item in order_line_ids %}`). A data function is only needed for computed values: amount in words, VAT, requisites. Dates and money are formatted by template filters: `{{ amount_total|money }}` → "1 234 567,80", `{{ date_order|date }}` → "30.09.2026", `{{ date_order|datetime }}`.

## Default templates

Template records are created by the seeder `report_docx/seed.py` — `seed_report_templates(env, specs)`: a module declares a list of specs (name, model, data function, type, format, path to the DOCX) and gets records with attached files in its `post_init`, nothing has to be created by hand. Idempotent by name: a deleted sample comes back after a restart, a renamed one stays; if the file could not be attached (no storage) the template is still created and the file is uploaded in the form. Your own samples are seeded with the same call from your module. `sales_report_docx` seeds:

| Template | Model | Data function | Type |
|----------|-------|---------------|------|
| Счёт на оплату (invoice) | `sales` | `sale_invoice_rus` | per record, PDF |
| Отчёт по продажам за период (sales for a period) | `sales` | `sales_period_data` | summary, PDF |
| Договор с клиентом, Договор с поставщиком, Договор-счёт, Дополнительное соглашение, Уведомление об уполномоченных лицах (contract documents) | `contract` | `contract_data` | per record, PDF |

`contract_data` (`sales_report_docx/models/contract_ext.py`, `@extend(Contract)`) fills the sample tags with our company's requisites (`c_*`, the director `our_dir` and `c_print_dir` from `chief_id`), the counterparty's (`partner_*`, bank `p_*`, phones and e-mail from its contacts), the contract dates (`contract_*`) and the lines of the contract's sales orders (`order_line`, `amount_total`, `amount_tax`). The models have no counterparty director (`customer_dir`, `p_print_dir`) or company phones — those tags stay empty until replaced in the designer. On the contract form the documents are available through the "Print" button.

## Template designer

The `report_docx_design` module (depends on `report_docx`, installed from the "Apps" page): the routes `POST /reports/preview` and `GET /reports/templates/{id}/fields`, the field catalog (`catalog.py`) and the frontend module `fara_report_docx_design`. Without it the engine works as before, and the "Designer" / "Configure template" buttons stay hidden (`isInstalled('report_docx_design')`).

The page `/report_template/{id}/design` ("Designer" button on the template form; for an administrator also in the record's "Print" menu, which puts that record into the preview). Three columns:

- **Editor** — the DOCX template in the built-in editor (the same one that edits docx attachments). Saving writes the file into the template's attachment; a template without a file gets a new document.
- **Fields** — the catalog from `GET /reports/templates/{id}/fields`: a click inserts the field at the caret as a Word content control with a label (`w:alias`) and a key (`w:tag`), holding a ready tag with a filter matching the type. Lists offer loop start/end buttons for a table row. The catalog merges two sources: the record model's fields and the data function keys declared by the `@report_fields` decorator from `report_docx/utils/fields.py` (it only marks the function, so modules with data functions do not depend on the designer):

```python title="sales_report_docx/models/sale_ext.py"
@staticmethod
@report_fields(
    bik="BIC", reciver="Recipient", summ=ReportField("Total", "money"),
    order_line=ReportList("Invoice lines", name="Name", qty="Qty"),
)
async def sale_invoice_rus(env, record_id: int) -> dict: ...
```

- **Preview** — after every edit (debounced) the editor hands over the document, the backend renders it with the selected record or parameters (`POST /reports/preview`, DOCX in base64) and the result is shown alongside: DOCX in view mode or PDF.

Content control wrappers are stripped before rendering (`utils/sdt.py`), so the output document and the PDF carry only the values. Templates are edited by administrators: the `report_template` ACL is read-only for `base_user` and full for `system_admin`; on databases where the module was already installed, tighten the old ACL row by hand: `UPDATE access_list SET perm_create=false, perm_update=false, perm_delete=false WHERE name='base_user_report_template'`.

## PDF

DOCX → PDF conversion has two modes, picked automatically:

| Mode | When | Result |
|------|------|--------|
| LibreOffice headless | `libreoffice`/`soffice` is installed | Exact Word layout. Included in the Docker image by default: build argument `WITH_LIBREOFFICE=1` (`.env`, +~400 MB, the layer is cached and not re-downloaded on `down`/`up`); `WITH_LIBREOFFICE=0` and `docker compose up -d --build` give an image without it. Without Docker — `apt install libreoffice-writer` |
| Built-in (python-docx + fpdf2) | LibreOffice not found | Text with emphasis, sizes and alignment, indents, numbered and bulleted lists, tables (per-cell borders — white and zero-width lines count as hidden, as in Word forms; merges, column widths), pictures in paragraphs and cells, floating pictures (the invoice stamp and signatures, at their anchor offset from the paragraph), page breaks |

An administrator sees which engine is active in the toolbar of the "Report templates" list: the badge "PDF: LibreOffice 7.6" or "PDF: built-in converter" (`GET /reports/pdf-engine`, administrators only). "Check again" (`?recheck=1`) looks for LibreOffice anew — after installing it on the server without a restart; "not found" is also re-checked once a minute in every worker. LibreOffice conversions run one at a time per process with a per-worker profile (`-env:UserInstallation`), otherwise parallel `soffice` runs interfere with each other.

The built-in mode does not carry headers/footers, colors, shapes or text wrapping — enough for "text + tables" forms (invoices, contracts, summaries). It needs a TTF font with Cyrillic glyphs: DejaVu Sans (`fonts-dejavu-core` package, already in the Dockerfile) or Arial (Windows, macOS). Without a font the conversion fails with a clear error.

## Scheduled sending

FARA cron runs "model + method" only (arbitrary code is disabled, see [Cron](../system/cron.md)), so the "build the report and send it" code lives in `report_template` model methods, while the job stores the method name and `kwargs`:

| Method | kwargs | Channel |
|--------|--------|---------|
| `cron_send_report_email` | `template_id`, `to`, `params`, optional `subject`, `text`, `connector_id` | Email with attachment through the chat email connector (SMTP) |
| `cron_send_report_telegram` | `template_id`, `chat_id`, `params`, optional `text`, `connector_id` | File to a Telegram chat through the bot connector |

`params` is the dict of parameters for the template's data function: the report is rebuilt on every run, so the data is always fresh. On startup the `sales_report_docx` module, along with the sample templates (see [Default templates](#default-templates)), creates two example jobs **disabled**: "Отправка еженедельных отчётов: пример (email)" and "… (Telegram)", weekly, with `params = {"days": 7}` and the `template_id` of "Отчёт по продажам за период". To enable a job:

1. Make sure the connector (email or telegram) is `active`.
2. Edit the job's `kwargs`: the address (`to`) or `chat_id` (Telegram chat/user id the bot is a member of; `@userinfobot` tells you yours), optionally `params` and `template_id`.
3. Set the interval and activate the job. "Run now" on the job form sends the report immediately — handy for checking.

```python title="what a job looks like"
await env.models.cron_job.create_or_update(
    env=env,
    name="Отправка еженедельных отчётов: пример (email)",
    model_name="report_template",
    method_name="cron_send_report_email",
    kwargs='{"template_id": 1, "to": "manager@example.com", "params": {"days": 7}}',
    interval_number=1, interval_type="weeks", active=False,
)
```

A "per employee" report is a data function too: it takes e.g. `user_id` in `params`, and the sending method loops over employees and sends each their own file. Another channel (internal chat, another messenger) is one more method modelled on the existing ones: build via `render_attachment`, send through the strategy of the matching connector.

## See also

- [Cron — background jobs](../system/cron.md)
- [Chat module](chat.md) — the email and Telegram connectors that deliver the files
