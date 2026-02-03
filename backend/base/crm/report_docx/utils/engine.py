"""
Движок генерации отчётов DOCX.
docxtpl + LibreOffice headless для PDF.
"""

import base64
import io
import logging
import os
import subprocess
import tempfile
from typing import Any

log = logging.getLogger(__name__)


class DocxReportEngine:
    """
    Рендер DOCX-шаблонов:
    - Jinja2: {{ variable }}, {% for %}, {% if %}
    - Замена изображений 1.jpg, 2.jpg (печати/подписи)
    - Конверсия PDF через LibreOffice
    """

    @staticmethod
    def render(
        template_bytes: bytes,
        context: dict[str, Any],
    ) -> bytes:
        """Рендерит DOCX-шаблон. Возвращает DOCX bytes."""
        from docxtpl import DocxTemplate

        templ = DocxTemplate(io.BytesIO(template_bytes))

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

        templ.render(context)

        output = io.BytesIO()
        templ.save(output)
        return output.getvalue()

    @staticmethod
    def convert_to_pdf(docx_bytes: bytes) -> bytes:
        """Конвертирует DOCX → PDF через LibreOffice headless."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "report.docx")
            with open(docx_path, "wb") as f:
                f.write(docx_bytes)

            lo_cmd = DocxReportEngine._find_libreoffice()

            try:
                result = subprocess.run(
                    [
                        lo_cmd,
                        "--headless",
                        "--norestore",
                        "--convert-to", "pdf",
                        "--outdir", tmpdir,
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

    @staticmethod
    def _find_libreoffice() -> str:
        for cmd in ["libreoffice", "soffice", "/usr/bin/libreoffice"]:
            try:
                r = subprocess.run(
                    [cmd, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                )
                if r.returncode == 0:
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return "libreoffice"

    @staticmethod
    def generate(
        template_bytes: bytes,
        context: dict[str, Any],
        output_format: str = "docx",
    ) -> tuple[bytes, str]:
        """
        Полный цикл: рендер + конверсия.
        Returns: (file_bytes, content_type)
        """
        docx_bytes = DocxReportEngine.render(template_bytes, context)

        if output_format == "pdf":
            pdf_bytes = DocxReportEngine.convert_to_pdf(docx_bytes)
            return pdf_bytes, "application/pdf"

        return (
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
