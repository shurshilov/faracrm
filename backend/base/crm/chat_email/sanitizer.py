# Copyright 2025 FARA CRM
# Email HTML sanitization - backend analog of frontend DOMPurify

"""
Санитизация HTML email сообщений перед сохранением в БД.

Использует только стандартную библиотеку Python (html.parser).
Конфигурация whitelist зеркалит фронтенд EmailMessageContent.tsx DOMPurify.
"""

import logging
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

# Whitelist тегов — зеркалит фронтенд DOMPurify config
ALLOWED_TAGS = {
    "p", "br", "b", "i", "u", "strong", "em", "a", "img",
    "div", "span", "blockquote", "pre", "code",
    "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "td", "th",
    "hr", "sub", "sup", "small",
}

# Whitelist атрибутов по тегам
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "*": {"style", "class"},
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "width", "height"},
    "td": {"width", "height"},
    "th": {"width", "height"},
}

# Разрешённые URL-схемы
SAFE_URL_SCHEMES = {"http", "https", "mailto"}

# Self-closing теги
VOID_TAGS = {"br", "hr", "img"}


def _is_safe_url(url: str) -> bool:
    """Проверяет что URL использует безопасную схему."""
    stripped = url.strip().lower()
    # Запрещаем javascript:, data:, vbscript: и т.д.
    if ":" in stripped:
        scheme = stripped.split(":", 1)[0].strip()
        return scheme in SAFE_URL_SCHEMES
    # Относительные URL и # — безопасны
    return True


class _Sanitizer(HTMLParser):
    """HTML parser который оставляет только whitelist теги и атрибуты."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.result: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return

        # Фильтруем атрибуты
        allowed = ALLOWED_ATTRIBUTES.get(tag, set()) | ALLOWED_ATTRIBUTES.get("*", set())
        safe_attrs = []
        for name, value in attrs:
            name = name.lower()
            if name not in allowed:
                continue
            # Проверяем URL атрибуты
            if name in ("href", "src") and value and not _is_safe_url(value):
                continue
            if value is None:
                safe_attrs.append(name)
            else:
                escaped = value.replace("&", "&amp;").replace('"', "&quot;")
                safe_attrs.append(f'{name}="{escaped}"')

        attr_str = (" " + " ".join(safe_attrs)) if safe_attrs else ""
        if tag in VOID_TAGS:
            self.result.append(f"<{tag}{attr_str} />")
        else:
            self.result.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.result.append(f"</{tag}>")

    def handle_data(self, data: str):
        self.result.append(
            data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    def handle_entityref(self, name: str):
        self.result.append(f"&{name};")

    def handle_charref(self, name: str):
        self.result.append(f"&#{name};")

    def handle_comment(self, data: str):
        pass  # Удаляем комментарии


def sanitize_email_html(html: str) -> str:
    """
    Санитизирует HTML email сообщения.

    Удаляет опасные теги (script, iframe, object, etc.),
    атрибуты (onclick, onerror, etc.), и протоколы (javascript:).

    Args:
        html: Сырой HTML из email

    Returns:
        Безопасный HTML
    """
    if not html:
        return html

    try:
        sanitizer = _Sanitizer()
        sanitizer.feed(html)
        return "".join(sanitizer.result)
    except Exception as e:
        logger.error(f"Email HTML sanitization failed: {e}")
        # Fallback: strip все теги
        sanitizer = _Sanitizer()
        sanitizer.result = []
        sanitizer.feed(html)
        # Вернуть только текст
        return html.replace("<", "&lt;").replace(">", "&gt;")
