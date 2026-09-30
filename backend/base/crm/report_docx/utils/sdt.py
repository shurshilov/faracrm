"""
Разворачивание content controls (w:sdt) в DOCX.

Конструктор отчётов вставляет теги как элементы управления Word: в редакторе
они подсвечены и подписаны (title = подпись поля, tag = ключ). Для рендера
обёртка не нужна и даже мешает: docxtpl подставит текст внутри, но `w:sdt`
уедет в готовый документ, а python-docx (встроенный PDF) не видит runs внутри
inline-элемента управления. Поэтому перед рендером обёртки снимаются: каждый
`w:sdt` заменяется содержимым своего `w:sdtContent` во всех частях пакета
(тело, колонтитулы, сноски).
"""

import io
import zipfile

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SDT = f"{{{W_NS}}}sdt"
_SDT_CONTENT = f"{{{W_NS}}}sdtContent"


def unwrap_content_controls(docx_bytes: bytes) -> bytes:
    """DOCX без w:sdt-обёрток. Пакет без них возвращается как есть."""
    source = zipfile.ZipFile(io.BytesIO(docx_bytes))
    changed: dict[str, bytes] = {}
    for info in source.infolist():
        if not (
            info.filename.startswith("word/")
            and info.filename.endswith(".xml")
        ):
            continue
        data = source.read(info.filename)
        if b"<w:sdt>" not in data and b"<w:sdt " not in data:
            continue
        root = etree.fromstring(data)
        if _unwrap(root):
            changed[info.filename] = etree.tostring(
                root, xml_declaration=True, encoding="UTF-8", standalone=True
            )
    if not changed:
        return docx_bytes

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            target.writestr(
                info, changed.get(info.filename, source.read(info.filename))
            )
    return output.getvalue()


def _unwrap(root: etree._Element) -> bool:
    """Заменяет каждый w:sdt детьми его w:sdtContent. Вложенные — по кругу."""
    changed = False
    while True:
        controls = root.findall(f".//{_SDT}")
        if not controls:
            return changed
        for sdt in controls:
            parent = sdt.getparent()
            if parent is None:
                continue
            index = parent.index(sdt)
            content = sdt.find(_SDT_CONTENT)
            for child in list(content) if content is not None else []:
                parent.insert(index, child)
                index += 1
            parent.remove(sdt)
            changed = True
