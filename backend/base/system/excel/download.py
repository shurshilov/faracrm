"""
Скачивание файлов по URL для импорта вложений.

Ссылку в ячейке даёт любой пользователь, поэтому сервер ходит только на
публичные адреса (иначе через импорт можно было бы опрашивать внутреннюю
сеть — SSRF): схема http/https, хост резолвится и проверяется на каждом
запросе, включая редиректы; размер файла и время ограничены.
"""

import asyncio
import ipaddress
import mimetypes
from pathlib import PurePosixPath
from urllib.parse import unquote

import httpx

MAX_SIZE = 20 * 1024 * 1024
TIMEOUT = 20.0
PARALLEL = 8


async def guard_request(request: httpx.Request) -> None:
    """Хук httpx: отказ, если адрес не публичный."""
    url = request.url
    if url.scheme not in ("http", "https"):
        raise ValueError("только http/https")
    infos = await asyncio.get_running_loop().getaddrinfo(url.host, None)
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError(f"адрес {url.host} не публичный")


async def fetch(client: httpx.AsyncClient, url: str) -> dict:
    """URL → поля вложения {name, mimetype, size, content}."""
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_SIZE:
                raise ValueError(f"файл больше {MAX_SIZE // 1024 // 1024} МБ")
            chunks.append(chunk)
    # Имя и тип — по конечному адресу (после редиректов) и заголовку.
    name = unquote(PurePosixPath(response.url.path).name) or "file"
    mimetype = (
        response.headers.get("content-type", "").split(";")[0].strip()
        or mimetypes.guess_type(name)[0]
        or "application/octet-stream"
    )
    return {
        "name": name,
        "mimetype": mimetype,
        "size": size,
        "content": b"".join(chunks),
    }


async def download_all(urls: set[str]) -> dict[str, dict | str]:
    """Каждый URL → поля вложения либо текст ошибки (ошибка строки, не
    всего импорта). Параллельно, не больше PARALLEL одновременно."""
    semaphore = asyncio.Semaphore(PARALLEL)
    results: dict[str, dict | str] = {}

    async def one(client: httpx.AsyncClient, url: str) -> None:
        async with semaphore:
            try:
                results[url] = await fetch(client, url)
            except Exception as e:  # noqa: BLE001
                results[url] = f"не удалось скачать {url}: {e}"

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        event_hooks={"request": [guard_request]},
    ) as client:
        await asyncio.gather(*(one(client, url) for url in urls))
    return results
