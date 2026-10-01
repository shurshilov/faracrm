"""
Движок генерации отчётов DOCX.
docxtpl + PDF: LibreOffice headless, если установлен, иначе простая
конвертация на python-docx + fpdf2 (docx_to_pdf.py).
"""

import base64
import datetime
import decimal
import functools
import io
import logging
import os
import pathlib
import re
import subprocess
import tempfile
import threading
import time
from typing import Any

from .sdt import unwrap_content_controls

log = logging.getLogger(__name__)

# «LibreOffice не найден» перепроверяем не чаще раза в минуту: у каждого
# воркера свой кэш, и после установки без рестарта они подхватят его сами
_LO_RECHECK_SECONDS = 60
# Конверсия через LibreOffice — по одной за раз в процессе (см. convert_to_pdf)
_LIBREOFFICE_LOCK = threading.Lock()


def _libreoffice_profile_uri() -> str:
    """Профиль LibreOffice этого процесса (file://…): у каждого воркера свой,
    чтобы они не блокировали друг друга через общий ~/.config."""
    path = os.path.join(
        tempfile.gettempdir(), f"fara_libreoffice_{os.getpid()}"
    )
    return pathlib.Path(path).as_uri()


def _probe_libreoffice() -> tuple[str, str] | None:
    """(команда, версия) LibreOffice или None, если он не установлен."""
    for cmd in ["libreoffice", "soffice", "/usr/bin/libreoffice"]:
        try:
            r = subprocess.run(
                [cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            output = r.stdout.decode("utf-8", errors="replace")
            found = re.search(r"\d+(?:\.\d+)+", output)
            return cmd, found.group(0) if found else output.strip()[:40]
    return None


# ---- Jinja-фильтры шаблонов: {{ amount_total|money }}, {{ date_order|date }} ----


def money_filter(value: Any) -> Any:
    """1234567.8 → «1 234 567,80»; не число — как есть."""
    if isinstance(value, bool) or not isinstance(
        value, (int, float, decimal.Decimal)
    ):
        return value
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def date_filter(value: Any, fmt: str = "%d.%m.%Y") -> Any:
    """date/datetime/ISO-строка → «30.09.2026»; остальное — как есть."""
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime(fmt)
    return value


def datetime_filter(value: Any, fmt: str = "%d.%m.%Y %H:%M") -> Any:
    return date_filter(value, fmt)


class DocxReportEngine:
    """
    Рендер DOCX-шаблонов:
    - Jinja2: {{ variable }}, {% for %}, {% if %} + фильтры money/date/datetime
    - Content controls конструктора (w:sdt) разворачиваются перед рендером
    - Замена изображений 1.jpg, 2.jpg (печати/подписи)
    - Конверсия PDF: LibreOffice (точная вёрстка) или встроенная простая
    """

    @staticmethod
    @functools.cache
    def jinja_env():
        """Окружение Jinja с фильтрами форматирования (одно на процесс).

        Песочница: шаблон — данные из базы (и из редактора конструктора),
        а не код проекта. Обычный Environment пускает из выражения в
        внутренности Python ({{ ''.__class__... }}) вплоть до выполнения
        команд на сервере; SandboxedEnvironment такие обращения отвергает.
        finalize: пустое значение печатается пустой строкой, а не «None».
        """
        from jinja2.sandbox import SandboxedEnvironment

        environment = SandboxedEnvironment(
            finalize=lambda value: "" if value is None else value
        )
        environment.filters.update(
            money=money_filter, date=date_filter, datetime=datetime_filter
        )
        return environment

    @staticmethod
    def render(
        template_bytes: bytes,
        context: dict[str, Any],
    ) -> bytes:
        """Рендерит DOCX-шаблон. Возвращает DOCX bytes."""
        from docxtpl import DocxTemplate

        templ = DocxTemplate(
            io.BytesIO(unwrap_content_controls(template_bytes))
        )

        # Замена изображений (печати/подписи) внутри docx
        # Шаблон содержит 1.jpg, 2.jpg, 3.jpg — заменяем на реальные
        images = context.pop("images", None)
        if images and isinstance(images, list):
            i = 1
            for image_data in images:
                if image_data and image_data is not False:
                    if isinstance(image_data, str):
                        imgdata = base64.b64decode(image_data)
                    elif isinstance(image_data, (bytes, bytearray)):
                        imgdata = bytes(image_data)
                    else:
                        i += 1
                        continue
                    templ.pic_to_replace[f"{i}.jpg"] = imgdata
                i += 1

        templ.render(context, jinja_env=DocxReportEngine.jinja_env())

        output = io.BytesIO()
        templ.save(output)
        return output.getvalue()

    @staticmethod
    def convert_to_pdf(docx_bytes: bytes, title: str | None = None) -> bytes:
        """Конвертирует DOCX → PDF.

        LibreOffice headless, если он есть в системе (точная вёрстка Word),
        иначе — простая конвертация без внешних программ (docx_to_pdf.py):
        текст, таблицы, картинки; без колонтитулов и точной вёрстки.
        title — заголовок PDF в метаданных (встроенный режим): его
        показывает вкладка просмотрщика и подставляет имя при сохранении.
        """
        lo_cmd = DocxReportEngine._find_libreoffice()
        if lo_cmd is None:
            try:
                from .docx_to_pdf import docx_to_pdf
            except ImportError as e:
                # Старый PyFPDF (fpdf 1.x) и fpdf2 ставятся под одним именем
                # модуля: с ним падает `fpdf.enums`. Нужен именно fpdf2.
                raise RuntimeError(
                    "PDF: нужен пакет fpdf2 из requirements.txt "
                    "(pip uninstall fpdf; pip install fpdf2), "
                    f"импорт не удался: {e}"
                ) from e

            return docx_to_pdf(docx_bytes, title)

        # Один профиль на процесс и одна конверсия за раз: два soffice с общим
        # профилем мешают друг другу (второй молча передаёт документ первому и
        # выходит без PDF), а свежий профиль на каждый вызов — это ещё +2 с
        with _LIBREOFFICE_LOCK, tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "report.docx")
            with open(docx_path, "wb") as f:
                f.write(docx_bytes)

            try:
                result = subprocess.run(
                    [
                        lo_cmd,
                        f"-env:UserInstallation={_libreoffice_profile_uri()}",
                        "--headless",
                        "--norestore",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        tmpdir,
                        docx_path,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60,
                )
                if result.returncode != 0:
                    stderr = result.stderr.decode("utf-8", errors="replace")
                    raise RuntimeError(f"LibreOffice error: {stderr}")
            except FileNotFoundError:
                raise RuntimeError(
                    "LibreOffice not found. Install: apt install libreoffice-writer"
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError("PDF conversion timed out (60s)")

            pdf_path = os.path.join(tmpdir, "report.pdf")
            if not os.path.exists(pdf_path):
                raise RuntimeError("PDF not created")

            with open(pdf_path, "rb") as f:
                return f.read()

    # (когда проверяли, что нашли) — кэш поиска LibreOffice на процесс
    _lo_probe: tuple[float, tuple[str, str] | None] = (0.0, None)

    @classmethod
    def _libreoffice_info(
        cls, recheck: bool = False
    ) -> tuple[str, str] | None:
        """(команда, версия) LibreOffice или None. Найденный помним весь срок
        процесса (проверка запускает процесс); «не найден» перепроверяем раз
        в минуту или сразу по recheck (кнопка «Проверить снова»)."""
        checked_at, info = cls._lo_probe
        if info is not None and not recheck:
            return info
        if not recheck and time.monotonic() - checked_at < _LO_RECHECK_SECONDS:
            return None
        info = _probe_libreoffice()
        cls._lo_probe = (time.monotonic(), info)
        return info

    @staticmethod
    def _find_libreoffice() -> str | None:
        """Команда LibreOffice или None, если он не установлен."""
        info = DocxReportEngine._libreoffice_info()
        return info[0] if info else None

    @staticmethod
    def pdf_engine_info(recheck: bool = False) -> dict[str, Any]:
        """Каким движком собираются PDF — для индикатора администратора:
        {"engine": "libreoffice"|"builtin", "path", "version"}."""
        info = DocxReportEngine._libreoffice_info(recheck)
        if info:
            return {
                "engine": "libreoffice",
                "path": info[0],
                "version": info[1],
            }
        return {"engine": "builtin", "path": None, "version": None}

    @staticmethod
    def generate(
        template_bytes: bytes,
        context: dict[str, Any],
        output_format: str = "docx",
        title: str | None = None,
    ) -> tuple[bytes, str]:
        """
        Полный цикл: рендер + конверсия (title — заголовок PDF, см.
        convert_to_pdf).
        Returns: (file_bytes, content_type)
        """
        docx_bytes = DocxReportEngine.render(template_bytes, context)

        if output_format == "pdf":
            pdf_bytes = DocxReportEngine.convert_to_pdf(docx_bytes, title)
            return pdf_bytes, "application/pdf"

        return (
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
