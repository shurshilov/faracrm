# Яндекс.Диск

`YandexDiskStrategy` — провайдер для Яндекс.Диска. Структурно повторяет [Google Drive стратегию](google.md), но проще: REST API напрямую через `httpx`, без специфичных SDK. Файлы адресуются путями, а не ID — это меняет поведение в нескольких местах.

## Когда выбирать

- Российская компания, нужно хранение на территории РФ.
- Уже есть подписка Яндекс 360.
- Не нужны Shared Drives как у Google — обычно достаточно одной шары на пользователя.

## API

Базовый URL — `https://cloud-api.yandex.net/v1/disk`. [Документация Яндекса](https://yandex.ru/dev/disk-api/doc/ref/).

Все вызовы — обычные REST через `httpx.AsyncClient`. Не нужна синхронная обёртка как у Google (googleapiclient).

## Авторизация — OAuth2

Стратегия хранит в `AttachmentStorage`:

<div class="field" markdown>
`yandex_client_id` / `yandex_client_secret` <span class="field-type">Char</span>

OAuth client из [oauth.yandex.ru](https://oauth.yandex.ru/).
</div>

<div class="field" markdown>
`yandex_access_token` / `yandex_refresh_token` <span class="field-type">Text</span>

Текущий и рефреш токены. Как у Google — access живёт ~1 час, refresh не протухает.
</div>

### Поток OAuth

Структурно идентичен Google — пользователь идёт на `oauth.yandex.ru`, авторизуется, возвращается с `code`, бэк меняет код на пару токенов. Особенность только в эндпоинтах:

```python
AUTH_URL  = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"
```

### Автообновление

`get_credentials()` проверяет, не пора ли обновлять access_token (если осталось < 5 мин). Если да — POST на `/token` с `grant_type=refresh_token`. Полученный новый access_token (и иногда новый refresh_token) сохраняется в `AttachmentStorage`.

## Адресация файлов — путь, а не ID

В отличие от Google Drive, где у каждого файла стабильный ID, в Яндекс.Диске **файл идентифицируется путём**:

```
/Disk/Sales Orders/SO-0000042-ClientA/contract.pdf
```

Это значит:

- При переименовании папки или файла "ID" фактически меняется.
- `Attachment.storage_file_id` и `storage_file_url` хранят **путь**, не идентификатор.
- При синхронизации FARA должна следить, чтобы пути совпадали — `enable_routes_cron` поможет переименовать папки, если изменился `name` записи.

## Особенность: follow_redirects

Это ключевой нюанс при работе с Яндекс.Диском, который легко упустить.

Запросы на скачивание (`/v1/disk/resources/download`) и заливку (`/v1/disk/resources/upload`) возвращают **302 редирект** на CDN-хост, а не сам файл/URL для аплоада. По умолчанию `httpx.AsyncClient` **не следует** редиректам (в отличие от `requests`).

```python
# ❌ Неверно — вернёт 302, не дойдёт до файла
async with httpx.AsyncClient() as client:
    response = await client.get(download_url)

# ✅ Правильно — следуем редиректу до CDN
async with httpx.AsyncClient(
    timeout=HTTP_TIMEOUT,
    follow_redirects=True,
) as client:
    response = await client.get(download_url)
```

Стратегия везде ставит `follow_redirects=True` — в `read_file`, `create_file` (upload), и при скачивании из публичного link.

!!! warning "Не забывайте этот флаг"
    Если делаешь свой код поверх стратегии (например, прямой fetch на Яндекс.Диск) — `follow_redirects=True` обязателен, иначе будут странные 302 в логах и пустые файлы.

## Структура папок

Та же логика, что и в Google: `pattern_root` + `pattern_record` из `AttachmentRoute`. Но без аналога Shared Drive — у Яндекс.Диска один корень `/Disk/` (или другая стартовая папка, если задана в настройках).

```
/Disk/
└── Sales Orders/                  ← pattern_root
    ├── SO-0000042-ClientA/        ← pattern_record
    │   ├── contract.pdf
    │   └── invoice.pdf
    └── SO-0000043-ClientB/
```

### Создание папок рекурсивно

Яндекс.Диск API **не создаёт промежуточные папки** при PUT `/resources?path=/A/B/C`. Если `/A/B` не существует, вернёт 409. Стратегия обходит это через `_ensure_folder_exists`:

```python
async def _ensure_folder_exists(self, path: str):
    """Рекурсивно создаёт всё дерево, начиная от ближайшей существующей папки."""
    parts = path.strip("/").split("/")
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        # Пытаемся создать; если 409 (уже есть) — игнорируем
        await self._create_folder_if_not_exists(current)
```

## Прочие методы

- **`create_file`** — двухфазный upload: получаем upload_url через `/resources/upload`, потом PUT с файлом на этот URL.
- **`read_file`** — получаем download_url через `/resources/download`, потом GET (с follow_redirects).
- **`update_file`** — Яндекс.Диск перезаписывает файл по тому же пути. Опция `overwrite=true`.
- **`delete_file`** — DELETE `/resources?path=...`. Файл попадает в корзину; есть опция `permanently=true` для жёсткого удаления.
- **`move_file`** — POST `/resources/move?from=...&path=...`. Используется при переименовании папок (`enable_routes_cron`).

## Лимиты

- **API**: 40 запросов/сек на токен. На массовых импортах FARA вставляет sleep между запросами.
- **Размер файла**: 50 ГБ через resumable upload, 1 ГБ через простой PUT. Стратегия использует resumable.
- **Объём диска**: зависит от тарифа Яндекс 360. Бесплатный — 5 ГБ.

## Когда лучше Google

Сравнение по делу:

| Критерий | Google Drive | Яндекс.Диск |
|----------|--------------|--------------|
| Работа из РФ | требует обходов | напрямую |
| Shared Drives | да (Workspace) | нет |
| Стабильность ID | да | нет (путь = ID) |
| Сложность OAuth | средняя | средняя (одинаково) |
| Latency из РФ | 200-500 ms | 50-150 ms |
| Цена за ГБ | выше | ниже |

## Известные особенности

!!! info "Async против google's sync SDK"
    Стратегия работает асинхронно через `httpx.AsyncClient` — не нужны `asyncio.to_thread()`-обёртки как в Google. Это примерно вдвое быстрее на bulk-операциях.

!!! warning "Cyrillic в путях"
    Яндекс.Диск принимает кириллические имена папок и файлов нормально. Но в URL они должны быть **percent-encoded**. `httpx` делает это сам при передаче через `params={"path": "..."}`, но если строишь URL вручную — `urllib.parse.quote(path)`.
