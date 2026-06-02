import hashlib
import json
from copy import deepcopy
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from urllib.parse import quote
from starlette.exceptions import HTTPException
from fastapi.responses import Response

from backend.project_info import VERSION
from backend.base.system.core.enviroment import env
from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.company.models.company import DEFAULT_MANIFEST
from ..app import AdministrationApp

router_public = APIRouter(
    tags=[f"{AdministrationApp.info.get("name")}"],
    dependencies=[
        Depends(
            AuthTokenApp.use_anonymous_session(
                ["company", "system_settings", "attachments"]
            )
        )
    ],
)

router_private = APIRouter(
    tags=[f"{AdministrationApp.info.get("name")}"],
    dependencies=[Depends(env.apps.auth.verify_access)],
)


@router_private.get("/apps/", response_model=dict)
def apps():
    apps = {}
    for app in env.apps.get_list():
        apps |= {f"{app.info.get("name")}": app.info}
    return apps


@router_public.get("/version/", response_model=str)
def version():
    return VERSION


class SocialLink(BaseModel):
    """Соцсеть на странице логина — пара (тип, ссылка)."""

    type: str
    url: str


class BrandingConfig(BaseModel):
    """Настройки бренда. URL-ы фронт строит сам через
    `${API_BASE_URL}/api/public/branding/<field>`."""

    has_logo: bool = False
    has_login_logo: bool = False
    has_login_background: bool = False
    # Кастомный фавикон для вкладки браузера и apple-touch-icon (не PWA).
    has_favicon: bool = False
    # Версия favicon-а для cache-bust. Меняется при загрузке новой картинки
    # (новый Attachment → новый id), заставляет браузер перетянуть файл.
    favicon_version: str | None = None
    # Загружены ли отдельные иконки для PWA-манифеста (192 / 512 px).
    has_manifest_icon_192: bool = False
    has_manifest_icon_512: bool = False
    # Версия PWA-манифеста. Меняется при изменении manifest_json или
    # любой из иконок (хеш по контенту). Фронт клеит её к URL манифеста
    # как `?v=<version>` — заставляет браузер/Android PWA перечитать.
    manifest_version: str | None = None
    # Заголовок вкладки браузера. Берётся из manifest_json.name (бэк
    # парсит). None → фронт оставляет значение из index.html.
    app_title: str | None = None
    login_title: str | None = None
    login_subtitle: str | None = None
    login_button_color: str | None = None
    login_card_style: str = "elevated"
    # Список соцсетей. Пустой список → фронт показывает дефолтные FARA-ссылки.
    # На бэке — 3 плоские пары полей login_socialN_type/url, в API
    # склеиваем в массив (без пустых) для удобства фронта.
    login_socials: list[SocialLink] = []


class PublicConfig(BaseModel):
    """Публичная конфигурация, доступная до логина."""

    version: str
    demo_mode: bool
    branding: BrandingConfig


async def _get_first_company():
    """Первая активная компания или None."""
    companies = await env.models.company.search(
        filter=[("active", "=", True)],
        order="asc",
        sort="sequence",
        limit=1,
        fields=[
            "id",
            "logo_id",
            "login_logo_id",
            "login_background_id",
            "favicon_id",
            "manifest_icon_192_id",
            "manifest_icon_512_id",
            "manifest_json",
            "login_title",
            "login_subtitle",
            "login_button_color",
            "login_card_style",
            "login_social1_type",
            "login_social1_url",
            "login_social2_type",
            "login_social2_url",
            "login_social3_type",
            "login_social3_url",
        ],
        fields_nested={
            "logo_id": ["id"],
            "login_logo_id": ["id"],
            "login_background_id": ["id"],
            "favicon_id": ["id"],
            "manifest_icon_192_id": ["id"],
            "manifest_icon_512_id": ["id"],
        },
    )
    return companies[0] if companies else None


# --- PWA manifest helpers --------------------------------------------------


def _ensure_manifest_dict(value: Any) -> dict[str, Any]:
    """JSONField обычно отдаёт dict, но если в БД лежит чужой мусор или
    None — fallback на DEFAULT_MANIFEST (со встроенными icons на
    /icon-*.png из public/). Лучше показать рабочий манифест, чем
    500-ить установку PWA.
    """
    if isinstance(value, dict):
        return value
    return deepcopy(DEFAULT_MANIFEST)


def _manifest_icons_from_company(company) -> list[dict[str, Any]]:
    """Собирает icons[] из загруженных файлов компании.

    Подставляется в манифест если в пользовательском JSON не задано icons.
    Это удобнее всего: админ грузит две картинки, JSON оставляет без icons —
    бэк сам прописывает правильные URL и размеры.
    """
    icons: list[dict[str, Any]] = []
    if getattr(company, "manifest_icon_192_id", None):
        icons.append(
            {
                "src": "/api/public/branding/manifest_icon_192_id",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            }
        )
    if getattr(company, "manifest_icon_512_id", None):
        icons.append(
            {
                "src": "/api/public/branding/manifest_icon_512_id",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            }
        )
    return icons


def _manifest_version(company) -> str | None:
    """Версия манифеста для cache-bust в URL.

    Хеш по контенту manifest_json + id'ам иконок: меняется при любой
    правке через админку. None → нечего показывать (нет ни JSON, ни иконок).
    """
    if company is None:
        return None
    parts: list[str] = []
    raw = getattr(company, "manifest_json", None)
    if raw:
        # dict → стабильный JSON (sort_keys чтобы порядок ключей не сбивал хеш).
        parts.append(
            json.dumps(raw, sort_keys=True, ensure_ascii=False)
            if isinstance(raw, dict)
            else str(raw)
        )
    for field in ("manifest_icon_192_id", "manifest_icon_512_id"):
        ref = getattr(company, field, None)
        if ref:
            parts.append(f"{field}:{ref.id}")
    if not parts:
        return None
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]


def _build_manifest(company) -> tuple[dict[str, Any], str]:
    """Финальный манифест + его ETag.

    1. Берём manifest_json как есть (dict из JSONB) либо fallback на
       DEFAULT_MANIFEST. В обоих случаях у нас уже валидный icons[]
       (либо то, что прописал admin в JSON, либо встроенные /icon-*.png).
    2. Если в Company загружены manifest_icon_192_id / manifest_icon_512_id —
       перекрываем icons[] на их URL. Логика: загрузка файла через форму —
       явный жест "вот моя иконка", он сильнее любого icons[] в JSON.
       Если admin хочет сохранить кастомные icons из JSON — пусть не
       загружает файлы (либо удалит manifest_icon_*).
    3. ETag — sha1 по итоговому JSON, для conditional GET (304).
    """
    manifest = _ensure_manifest_dict(getattr(company, "manifest_json", None))
    company_icons = _manifest_icons_from_company(company)
    if company_icons:
        manifest["icons"] = company_icons
    body = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    etag = hashlib.sha1(body).hexdigest()
    return manifest, etag


def _collect_social_links(company) -> list[SocialLink]:
    """Собирает массив непустых соцсетей из плоских полей компании.

    Пропускаем пары где type или url пустые — на фронте такие ссылки
    всё равно не отрисовать.
    """
    result: list[SocialLink] = []
    for i in (1, 2, 3):
        type_ = getattr(company, f"login_social{i}_type", None)
        url = getattr(company, f"login_social{i}_url", None)
        if type_ and url:
            result.append(SocialLink(type=type_, url=url))
    return result


def _title_from_manifest(value: Any) -> str | None:
    """Имя приложения для <title> вкладки. Берём name из manifest_json —
    отдельного поля app_title в Company больше нет.
    """
    if not isinstance(value, dict):
        return None
    name = value.get("name") or value.get("short_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


@router_public.get("/public/config/", response_model=PublicConfig)
async def public_config():
    """Конфиг для фронта (страница логина и т.п.)."""
    demo = await env.models.system_settings.get_value(
        "ui.demo_mode", default=False
    )
    company = await _get_first_company()
    branding = (
        BrandingConfig()
        if company is None
        else BrandingConfig(
            has_logo=bool(company.logo_id),
            has_login_logo=bool(company.login_logo_id),
            has_login_background=bool(company.login_background_id),
            has_favicon=bool(company.favicon_id),
            favicon_version=(
                str(company.favicon_id.id) if company.favicon_id else None
            ),
            has_manifest_icon_192=bool(company.manifest_icon_192_id),
            has_manifest_icon_512=bool(company.manifest_icon_512_id),
            manifest_version=_manifest_version(company),
            app_title=_title_from_manifest(company.manifest_json),
            login_title=company.login_title or None,
            login_subtitle=company.login_subtitle or None,
            login_button_color=company.login_button_color or None,
            login_card_style=company.login_card_style or "elevated",
            login_socials=_collect_social_links(company),
        )
    )
    return PublicConfig(
        version=VERSION, demo_mode=bool(demo), branding=branding
    )


@router_public.get("/public/manifest.json")
async def public_manifest(request: Request):
    """PWA-манифест из настроек компании.

    Зачем эта ручка вообще существует, если есть статичный
    /manifest.json во frontend/public/:
    — Статика не позволяет менять name/иконки без передеплоя.
      Android при установке PWA фиксирует имя и иконку из манифеста на
      момент установки — поэтому нам критично иметь возможность
      обновлять манифест и заставлять браузер его перечитать.
    — Здесь Cache-Control: no-cache + ETag, и icons[] подставляются
      из загруженных файлов компании. Фронт указывает на эту ручку
      через <link rel="manifest"> + ?v=<manifest_version>.
    """
    company = await _get_first_company()
    if company is None:
        manifest: dict[str, Any] = deepcopy(DEFAULT_MANIFEST)
        body = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
        etag = hashlib.sha1(body).hexdigest()
    else:
        manifest, etag = _build_manifest(company)

    quoted_etag = f'"{etag}"'
    # Conditional GET — если у клиента уже свежая версия, отдаём 304.
    # no-cache заставляет браузер всегда делать запрос, must-revalidate —
    # запрещает использовать stale-копию даже офлайн.
    if request.headers.get("if-none-match") == quoted_etag:
        return Response(
            status_code=304,
            headers={
                "ETag": quoted_etag,
                "Cache-Control": "no-cache, must-revalidate",
            },
        )

    body = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/manifest+json",
        headers={
            "ETag": quoted_etag,
            "Cache-Control": "no-cache, must-revalidate",
        },
    )


@router_public.get("/public/branding/{field}")
async def branding_file(
    field: Literal[
        "logo_id",
        "login_logo_id",
        "login_background_id",
        "favicon_id",
        "manifest_icon_192_id",
        "manifest_icon_512_id",
    ],
):
    """Публичная отдача файла из Company.<field>.

    Использует sudo() для доступа к Attachment по конкретному ID —
    AnonymousSession имеет READ только к whitelist'у, и хотя attachments
    в нём, для удобства идём через sudo (явный обход).
    """

    company = await _get_first_company()
    if company is None or not getattr(company, field, None):
        raise HTTPException(status_code=404)

    attachment_ref = getattr(company, field)
    attachment_id = attachment_ref.id

    attaches = await env.models.attachment.search(
        filter=[("id", "=", attachment_id)],
        limit=1,
        fields=[
            "id",
            "name",
            "mimetype",
            "storage_file_url",
            "storage_file_id",
            "storage_id",
            "content",
        ],
        fields_nested={"storage_id": ["id", "type", "google_credentials"]},
    )
    if not attaches:
        raise HTTPException(status_code=404)

    attach = attaches[0]
    return Response(
        # Без filename* браузер не переведет проценты обратно в буквы
        headers={
            "Content-Disposition": f"inline; filename*=utf-8''{quote(attach.name, safe='')}",
            "Cache-Control": "public, max-age=300",
        },
        media_type=attach.mimetype,
        content=await attach.read_content(),
    )
