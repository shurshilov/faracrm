# Отчёты DOCX и рассылка по расписанию

Модуль `report_docx` — движок: собирает документы (счета, договоры, сводные отчёты) из DOCX-шаблонов с Jinja2-тегами, отдаёт результат как DOCX или PDF и умеет отправлять готовый файл по расписанию — на почту или в Telegram. Функции данных и образцы шаблонов живут в модулях предметных областей: для продаж это `sales_report_docx`. Конструктор шаблонов в браузере — отдельный модуль `report_docx_design`.

## Как устроен шаблон

Шаблон — запись `report_template` (меню «Шаблоны отчётов»):

<div class="field" markdown>
`python_function` <span class="field-type">Char</span>

Имя функции данных: `@staticmethod` вида `async def name(env, **params) -> dict`. Она собирает **дикт данных**, ключи которого — теги шаблона. Откуда берутся данные, решает функция: из одной записи (`params = {"record_id": id}`), из выборки за период, из нескольких моделей. Список `images` (bytes или base64) подменяет картинки `1.jpg`, `2.jpg`… в шаблоне — так подставляются печать и подписи.
</div>

<div class="field" markdown>
`model_name` <span class="field-type">Char</span>

Модель, на которой лежит функция данных, по имени таблицы, как в `/auto/{model}`: `sales`, `partners`. Кнопка «Печать» — часть ядра (`components/Form/PrintButton.tsx`, тулбар каждой формы): модуль регистрирует в ней свой источник пунктов (`fara_report_docx/extensions.ts` → `registerPrintProvider`), и она показывается, как только у модели появляется хотя бы один активный шаблон по записи. Подключать что-либо в формы не нужно.
</div>

<div class="field" markdown>
`report_type` <span class="field-type">record | summary</span>

`record` — документ по записи: функция получает `record_id`, шаблон виден в меню «Печать». `summary` — сводный отчёт: записи нет, параметры функции приходят из cron-задачи или роута, в меню «Печать» шаблон не показывается.
</div>

<div class="field" markdown>
`template_file` <span class="field-type">Attachment</span>

DOCX-файл с тегами `{{ tag }}`, `{% for %}`, `{% if %}`, в таблицах `{%tr for %}` (движок docxtpl). Образцы лежат в `backend/base/crm/sales_report_docx/templates/` (счёт на оплату, договоры, отчёт по продажам за период) и при старте сеются записями шаблонов, см. [Шаблоны по умолчанию](#default-templates).
</div>

<div class="field" markdown>
`output_format` <span class="field-type">docx | pdf</span>

Формат по умолчанию; роут принимает `?output_format=` для переопределения.
</div>

Функции данных по продажам собраны в `sales_report_docx/models/sale_ext.py` (`@extend(Sale)`), два вида:

```python title="документ по записи — report_type = record"
@staticmethod
async def sale_invoice_rus(env: "Environment", record_id: int) -> dict:
    sale = await env.models.sale.search_one(filter=[("id", "=", record_id)], ...)
    return {"so_number": sale.name, "customer": ..., "order_line": [...]}
```

```python title="сводный отчёт — report_type = summary"
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

`sales_period_data` — рабочий пример «продажи за последние N дней» с итогами по менеджерам; шаблон к нему — `sales_report_docx/templates/Отчёт по продажам за период.docx`. Свой отчёт — такая же функция в своём модуле (или в `backend/business`): любые запросы, любые ключи, DOCX с тегами по её ключам.

Сборка идёт через `ReportTemplate.render_attachment(template_id, params=None, output_format=None)`: метод зовёт `python_function(env, **params)` и возвращает несохранённый `Attachment` (имя, mimetype, содержимое). Его используют роут и рассылки:

| Роут | Что делает |
|------|------------|
| `GET /reports/generate/{template_id}/{record_id}` | Документ по записи: `params = {"record_id": record_id}` (кнопка «Печать») |
| `GET /reports/generate/{template_id}?params={"days":30}` | Сводный отчёт: параметры функции данных JSON-объектом |

Для документа по записи в контекст, кроме дикта функции, попадают **все поля записи** (`ReportTemplate.record_context`): скаляры как есть, связи Many2one на один уровень (`{{ partner_id.name }}`), списки One2many/Many2many — как строки (`{%tr for item in order_line_ids %}`). Функция данных нужна только для вычисляемого: суммы прописью, НДС, реквизитов. Даты и деньги форматируют фильтры шаблона: `{{ amount_total|money }}` → «1 234 567,80», `{{ date_order|date }}` → «30.09.2026», `{{ date_order|datetime }}`.

## Шаблоны по умолчанию { #default-templates }

Записи шаблонов создаёт сидер `report_docx/seed.py` — `seed_report_templates(env, specs)`: модуль объявляет список спецификаций (имя, модель, функция данных, тип, формат, путь к DOCX) и в `post_init` получает записи с привязанными файлами, руками ничего создавать не нужно. Идемпотентно по имени: удалённый образец вернётся после рестарта, переименованный — останется; если файл не удалось привязать (нет хранилища), шаблон всё равно создаётся, файл догружают в форме. Свои образцы сеют тем же вызовом из своего модуля. `sales_report_docx` сеет:

| Шаблон | Модель | Функция данных | Тип |
|--------|--------|----------------|-----|
| Счёт на оплату | `sales` | `sale_invoice_rus` | по записи, PDF |
| Отчёт по продажам за период | `sales` | `sales_period_data` | сводный, PDF |
| Договор с клиентом, Договор с поставщиком, Договор-счёт, Дополнительное соглашение, Уведомление об уполномоченных лицах | `contract` | `contract_data` | по записи, PDF |

`contract_data` (`sales_report_docx/models/contract_ext.py`, `@extend(Contract)`) собирает под теги образцов реквизиты своей компании (`c_*`, руководитель `our_dir` и `c_print_dir` из `chief_id`), контрагента (`partner_*`, банк `p_*`, телефоны и e-mail из его контактов), даты договора (`contract_*`) и строки заказов по договору (`order_line`, `amount_total`, `amount_tax`). Руководителя контрагента (`customer_dir`, `p_print_dir`) и телефонов компании в моделях нет — эти теги пустые, пока их не заменят в конструкторе. На форме договора документы доступны кнопкой «Печать».

## Конструктор шаблона

Модуль `report_docx_design` (зависит от `report_docx`, ставится со страницы «Приложения»): роуты `POST /reports/preview` и `GET /reports/templates/{id}/fields`, каталог полей (`catalog.py`) и фронтовый модуль `fara_report_docx_design`. Без него движок работает как раньше, а кнопки «Конструктор» и «Настроить шаблон» на фронте не показываются (`isInstalled('report_docx_design')`).

Страница `/report_template/{id}/design` (кнопка «Конструктор» на форме шаблона, для администратора — ещё и в меню «Печать» записи, тогда запись сразу подставляется в превью). Три колонки:

- **Редактор** — DOCX-шаблон во встроенном редакторе (тот же, что правит docx-вложения). Сохранение пишет файл в вложение шаблона; у шаблона без файла документ создаётся с нуля.
- **Поля** — каталог `GET /reports/templates/{id}/fields`: клик вставляет поле в позицию курсора как content control Word с подписью (`w:alias`) и ключом (`w:tag`), внутри — готовый тег с фильтром по типу. Списки дают кнопки начала и конца цикла для строки таблицы. Каталог собирают два источника: поля модели записи и ключи функции данных, объявленные декоратором `@report_fields` из `report_docx/utils/fields.py` (он только помечает функцию, поэтому модули с функциями данных от конструктора не зависят):

```python title="sales_report_docx/models/sale_ext.py"
@staticmethod
@report_fields(
    bik="БИК", reciver="Получатель", summ=ReportField("Итого", "money"),
    order_line=ReportList("Позиции счёта", name="Наименование", qty="Кол-во"),
)
async def sale_invoice_rus(env, record_id: int) -> dict: ...
```

- **Превью** — после каждой правки (с задержкой) редактор отдаёт документ, бэк рендерит его с данными выбранной записи или параметров (`POST /reports/preview`, DOCX в base64) и результат показывается рядом: DOCX в режиме просмотра или PDF.

Перед рендером обёртки content controls снимаются (`utils/sdt.py`), поэтому в готовом документе и в PDF остаются только значения. Править шаблоны могут администраторы: ACL `report_template` у `base_user` — только чтение, у `system_admin` — полный; на базах, где модуль уже стоял, старую строку ACL нужно ужать вручную: `UPDATE access_list SET perm_create=false, perm_update=false, perm_delete=false WHERE name='base_user_report_template'`.

## Права и безопасность

Отчёт печатается от имени того, кто нажал кнопку: `record_context` и функция данных читают записи под сессией запроса, то есть с ACL модели и правилами строк этого пользователя. Запись, которую он не может открыть, в документ не попадёт: роут ответит отказом. Рассылки cron собирают отчёт под системной сессией.

Поля закрываются на уровне контекста: в него не входят приватные поля (`private=True` — хэши паролей, токены хранилищ), поля с ролевым доступом (`role_read`, `role_create`, `role_update` — например, вебхуки и токены коннекторов) и байты. То же правило для связей: у Many2one и списков берутся только публичные скаляры без ролевых ограничений. Тег на такое поле печатается пустым. Функция данных пишется разработчиком и читает базу через ORM, где `role_read` вырезает закрытые поля и в прямом поиске, и во вложенных связях (`fields_nested`); приватные поля ORM отдаёт серверному коду, поэтому в дикт функции их класть нельзя.

Шаблон исполняется Jinja в песочнице (`SandboxedEnvironment`): обращения к внутренностям Python (`{{ ''.__class__… }}`) отвергаются, пустое значение печатается пустой строкой. Роуты конструктора (`POST /reports/preview`, `GET /reports/templates/{id}/fields`) и индикатор движка PDF — только администратору отчётов (суперпользователь или роль `system_admin`, как ACL `report_template`): превью исполняет присланный клиентом DOCX. Тесты: `tests/unit/test_report_docx_engine.py`, `tests/integration/report_docx/`.

## PDF

Конверсия DOCX → PDF работает в двух режимах, выбор автоматический:

| Режим | Когда | Что даёт |
|-------|-------|----------|
| LibreOffice headless | В системе есть `libreoffice`/`soffice` | Точная вёрстка Word. В Docker-образ входит по умолчанию: аргумент сборки `WITH_LIBREOFFICE=1` (`.env`, +~400 МБ, слой кэшируется и при `down`/`up` не перекачивается); `WITH_LIBREOFFICE=0` и `docker compose up -d --build` дают образ без него. Без Docker — `apt install libreoffice-writer` |
| Встроенный (python-docx + fpdf2) | LibreOffice не найден | Текст с начертаниями, размерами и выравниванием, отступы, нумерованные и маркированные списки, таблицы (границы по каждой ячейке — белые и нулевые линии считаются скрытыми, как в формах Word; объединения, ширины колонок), картинки в абзацах и ячейках, плавающие картинки (печать и подписи счёта — в точке их привязки к абзацу), разрывы страниц |

Какой движок работает, администратор видит в тулбаре списка «Шаблоны отчётов»: бейдж «PDF: LibreOffice 7.6» или «PDF: встроенный конвертер» (`GET /reports/pdf-engine`, только администратору). Кнопка «Проверить снова» (`?recheck=1`) ищет LibreOffice заново — после установки на сервер без рестарта; «не найден» и сам перепроверяется раз в минуту в каждом воркере. Конверсии через LibreOffice идут по одной на процесс и с отдельным профилем на воркер (`-env:UserInstallation`), иначе параллельные `soffice` мешают друг другу.

Встроенный режим не переносит колонтитулы, цвета, фигуры и обтекание текстом — для форм «текст + таблицы» (счета, договоры, сводки) этого достаточно. Ему нужен TTF-шрифт с кириллицей: DejaVu Sans (пакет `fonts-dejavu-core`, уже в Dockerfile) или Arial (Windows, macOS). Без шрифта конверсия вернёт понятную ошибку.

## Отправка по расписанию

Cron в FARA исполняет только «модель + метод» (произвольный код отключён, см. [Cron](../system/cron.md)), поэтому код «собрать отчёт и отправить» живёт в методах модели `report_template`, а задача хранит имя метода и `kwargs`:

| Метод | kwargs | Куда |
|-------|--------|------|
| `cron_send_report_email` | `template_id`, `to`, `params`, опц. `subject`, `text`, `connector_id` | Письмо с вложением через email-коннектор чата (SMTP) |
| `cron_send_report_telegram` | `template_id`, `chat_id`, `params`, опц. `text`, `connector_id` | Файл в Telegram-чат через коннектор бота |

`params` — дикт параметров функции данных шаблона: при каждом запуске отчёт собирается заново, поэтому данные всегда свежие. Модуль `sales_report_docx` при старте вместе с шаблонами-образцами (см. [Шаблоны по умолчанию](#default-templates)) создаёт две задачи-примера **выключенными**: «Отправка еженедельных отчётов: пример (email)» и «… (Telegram)», раз в неделю, с `params = {"days": 7}` и `template_id` шаблона «Отчёт по продажам за период». Чтобы включить рассылку:

1. Проверьте, что коннектор (email или telegram) `active`.
2. В задаче cron поправьте `kwargs`: адрес (`to`) или `chat_id` (id чата/пользователя Telegram, где состоит бот; свой id подскажет `@userinfobot`), при желании `params` и `template_id`.
3. Поставьте интервал и включите задачу. Кнопка «Запустить сейчас» на форме задачи отправит отчёт немедленно — удобно для проверки.

```python title="как выглядит задача"
await env.models.cron_job.create_or_update(
    env=env,
    name="Отправка еженедельных отчётов: пример (email)",
    model_name="report_template",
    method_name="cron_send_report_email",
    kwargs='{"template_id": 1, "to": "manager@example.com", "params": {"days": 7}}',
    interval_number=1, interval_type="weeks", active=False,
)
```

Отчёт «по каждому сотруднику» — тоже функция данных: она принимает, например, `user_id` в `params`, а метод-рассыльщик обходит сотрудников циклом и шлёт каждому его файл. Свой канал (внутренний чат, другой мессенджер) — ещё один метод по образцу существующих: собрать через `render_attachment`, отправить стратегией нужного коннектора.

## См. также

- [Cron — фоновые задачи](../system/cron.md)
- [Модуль чата](chat.md) — коннекторы email и Telegram, через которые уходят файлы
