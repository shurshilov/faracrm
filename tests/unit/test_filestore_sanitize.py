"""
Unit tests for filestore.sanitize_filename.

Покрывают best-practice требования (state of the art 2024-2026):
- Сохранение Unicode (кириллица, эмодзи, китайский) — НЕ выкидываем.
- Удаление только control chars / path separators / Windows-reserved.
- NFC-нормализация.
- Path traversal защита (../).
- Fallback на пустые / "." / ".." / только-точки имена.
- Windows-reserved имена (CON, PRN, NUL...) получают префикс.
- Длина обрезается в БАЙТАХ (не символах) с сохранением расширения
  и валидной UTF-8 границы.

No database, no filesystem. Pure function tests.

Run: pytest tests/unit/test_filestore_sanitize.py -v -m unit
"""

import unicodedata

import pytest

from backend.base.crm.attachments.strategies.filestore import (
    sanitize_filename,
    slugify_filename,
)

pytestmark = pytest.mark.unit


# =====================================================================
# Сохранение Unicode — главный регресс старой реализации
# (старая slugify через NFKD + ascii ignore теряла кириллицу полностью)
# =====================================================================


class TestUnicodePreserved:
    """Юникод-имена сохраняются как есть (после NFC-нормализации)."""

    def test_cyrillic_name_preserved(self):
        # Раньше превращалось в ".pdf" — главный баг для русскоязычных юзеров
        assert (
            sanitize_filename("Отчёт за квартал.pdf") == "Отчёт за квартал.pdf"
        )

    def test_cyrillic_extension_preserved(self):
        assert sanitize_filename("документ.документ") == "документ.документ"

    def test_chinese_preserved(self):
        assert sanitize_filename("报告.pdf") == "报告.pdf"

    def test_arabic_preserved(self):
        assert sanitize_filename("تقرير.pdf") == "تقرير.pdf"

    def test_emoji_preserved(self):
        # Современные FS (ext4, NTFS, APFS) поддерживают эмодзи
        assert sanitize_filename("vacation 🏖️.jpg") == "vacation 🏖️.jpg"

    def test_mixed_script_preserved(self):
        assert sanitize_filename("Q4 отчёт 2024.xlsx") == "Q4 отчёт 2024.xlsx"

    def test_spaces_preserved(self):
        # Пробелы внутри имени допустимы
        assert sanitize_filename("my report.pdf") == "my report.pdf"

    def test_parentheses_preserved(self):
        # Скобки — обычный символ, не опасный
        assert sanitize_filename("file (copy).txt") == "file (copy).txt"

    def test_double_extension_preserved(self):
        # Старый slugify ломал .tar.gz → .gz с потерей tar.
        # Это критично для архивов.
        assert sanitize_filename("archive.tar.gz") == "archive.tar.gz"

    def test_case_preserved(self):
        # Не приводим к нижнему регистру — имя пользователя
        assert sanitize_filename("Photo.JPG") == "Photo.JPG"


# =====================================================================
# NFC-нормализация
# =====================================================================


class TestNFCNormalization:
    """Имена нормализуются в NFC — каноничную форму для FS."""

    def test_decomposed_to_composed(self):
        # "é" может быть представлен как U+00E9 (composed)
        # или U+0065 + U+0301 (decomposed). NFC даёт первое.
        decomposed = "cafe\u0301.txt"  # cafe + combining acute = café
        composed = "café.txt"  # пред-комбинированный
        assert sanitize_filename(decomposed) == composed
        # Защищаемся от теста на саму себя
        assert decomposed != composed

    def test_already_nfc_unchanged(self):
        already_nfc = unicodedata.normalize("NFC", "Привет.txt")
        assert sanitize_filename(already_nfc) == already_nfc


# =====================================================================
# Удаление опасных символов
# =====================================================================


class TestDangerousCharsRemoved:
    """Удаляются только реально опасные символы."""

    def test_null_byte_removed(self):
        # NULL byte ломает open() в Python
        assert sanitize_filename("file\x00.exe") == "file.exe"

    def test_control_chars_removed(self):
        # \n, \t, \r и прочие управляющие — убираем
        assert sanitize_filename("file\nname\t.txt") == "filename.txt"
        assert sanitize_filename("a\rb\x07c.txt") == "abc.txt"

    def test_path_separator_forward_removed(self):
        # / удаляется (basename должен срабатывать, но защита двойная)
        # basename "../../etc/passwd" → "passwd"
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_path_separator_backslash_removed(self):
        # Windows-стиль path traversal
        assert sanitize_filename("..\\..\\windows\\system32\\foo") == "foo"

    def test_windows_reserved_chars_removed(self):
        # < > : " | ? * — Windows-reserved
        assert sanitize_filename('a<b>c:d"e|f?g*h.txt') == "abcdefgh.txt"

    def test_safe_punctuation_kept(self):
        # !@#$%^&()-_=+[]{};', — не опасны на FS, оставляем
        assert sanitize_filename("file!@#$.txt") == "file!@#$.txt"
        assert sanitize_filename("file_name-v1.0.txt") == "file_name-v1.0.txt"


# =====================================================================
# Path traversal
# =====================================================================


class TestPathTraversal:
    """Защита от path traversal через basename."""

    def test_dotdot_slash(self):
        # basename выдёргивает только последний компонент
        assert sanitize_filename("../etc/passwd") == "passwd"

    def test_absolute_path(self):
        assert sanitize_filename("/etc/shadow") == "shadow"

    def test_nested_traversal(self):
        assert sanitize_filename("../../../../root/.ssh/id_rsa") == "id_rsa"


# =====================================================================
# Edge cases: пустое, точки, специмена
# =====================================================================


class TestFallback:
    """Спецслучаи дают детерминированный fallback вместо crash/пустоты."""

    def test_empty_string(self):
        assert sanitize_filename("") == "file"

    def test_none_input(self):
        # Нечасто, но защищаемся: filename or "" в начале функции
        assert sanitize_filename(None) == "file"

    def test_dot(self):
        # "." — спецзапись текущей директории, нельзя сделать таким файл
        assert sanitize_filename(".") == "file"

    def test_dotdot(self):
        assert sanitize_filename("..") == "file"

    def test_only_dots(self):
        # "..." после strip(".") становится "", даём fallback
        assert sanitize_filename("...") == "file"

    def test_only_whitespace(self):
        assert sanitize_filename("   ") == "file"

    def test_only_forbidden(self):
        # После удаления всех символов — пусто, fallback
        assert sanitize_filename("\x00\x01\x02") == "file"

    def test_custom_fallback(self):
        assert sanitize_filename("", fallback="unnamed") == "unnamed"
        assert sanitize_filename("...", fallback="x") == "x"

    def test_trailing_dot_stripped(self):
        # "a." → "a" (Windows не любит trailing dot)
        assert sanitize_filename("report.") == "report"

    def test_trailing_whitespace_stripped(self):
        assert sanitize_filename("report.txt   ") == "report.txt"

    def test_leading_whitespace_stripped(self):
        assert sanitize_filename("   report.txt") == "report.txt"


# =====================================================================
# Windows reserved имена
# =====================================================================


class TestWindowsReservedNames:
    """CON, PRN, NUL, COM1..LPT9 — префиксуем подчёркиванием."""

    def test_con_prefixed(self):
        assert sanitize_filename("CON.txt") == "_CON.txt"

    def test_con_lowercase_also_prefixed(self):
        # Регистронезависимое сравнение
        assert sanitize_filename("con.txt") == "_con.txt"

    def test_nul_prefixed(self):
        assert sanitize_filename("NUL.log") == "_NUL.log"

    def test_com1_prefixed(self):
        assert sanitize_filename("COM1.txt") == "_COM1.txt"

    def test_lpt9_prefixed(self):
        assert sanitize_filename("LPT9.dat") == "_LPT9.dat"

    def test_conrad_not_affected(self):
        # CONRAD не в списке reserved — не трогаем
        assert sanitize_filename("CONRAD.txt") == "CONRAD.txt"

    def test_normal_name_not_affected(self):
        assert sanitize_filename("report.txt") == "report.txt"


# =====================================================================
# Длина в байтах (не символах)
# =====================================================================


class TestByteLengthLimit:
    """Обрезка по 255 байт с сохранением расширения и валидного UTF-8."""

    def test_short_name_unchanged(self):
        assert sanitize_filename("short.txt") == "short.txt"

    def test_long_ascii_truncated_with_ext(self):
        # 500 ASCII букв = 500 байт, ext .txt = 4 байта → name 251 байт
        result = sanitize_filename("a" * 500 + ".txt")
        assert result.endswith(".txt")
        assert len(result.encode("utf-8")) <= 255
        # Имя содержит максимум "a"
        assert result == "a" * 251 + ".txt"

    def test_long_unicode_truncated_correctly(self):
        # Кириллица — 2 байта на символ. 200 символов = 400 байт.
        # После обрезки имя должно быть валидным UTF-8 (не битые байты).
        result = sanitize_filename("я" * 200 + ".txt")
        assert result.endswith(".txt")
        assert len(result.encode("utf-8")) <= 255
        # Должен корректно декодироваться (errors="ignore" срезал хвост)
        result.encode("utf-8").decode("utf-8")  # не должно бросить

    def test_emoji_truncated_correctly(self):
        # Эмодзи — 4 байта на символ.
        # 100 эмодзи = 400 байт. Обрезка не должна разбить эмодзи пополам.
        emoji_name = "🎉" * 100 + ".txt"
        result = sanitize_filename(emoji_name)
        assert result.endswith(".txt")
        assert len(result.encode("utf-8")) <= 255
        # Декодирование должно пройти без ошибок и без replacement chars
        decoded = result.encode("utf-8").decode("utf-8")
        assert "\ufffd" not in decoded

    def test_extension_preserved_at_truncation(self):
        # Расширение всегда должно остаться целым
        result = sanitize_filename("x" * 1000 + ".pdf")
        assert result.endswith(".pdf")

    def test_huge_extension_handled(self):
        # Экзотика: расширение само длиннее 255 байт.
        # Не должно падать, должно вернуть что-то валидное в 255 байт.
        result = sanitize_filename("a." + "b" * 300)
        assert len(result.encode("utf-8")) <= 255


# =====================================================================
# Реальные пользовательские кейсы
# =====================================================================


class TestRealWorldCases:
    """Сценарии из жизни."""

    def test_screenshot_typical(self):
        assert (
            sanitize_filename("Screenshot 2024-01-15 at 10.30.45.png")
            == "Screenshot 2024-01-15 at 10.30.45.png"
        )

    def test_dotfile(self):
        # ".gitignore": splitext → ("", ".gitignore")
        # name=="" попадёт в "" / "." / ".." → fallback?
        # На самом деле: после basename ".gitignore", strip().rstrip(".")
        # → ".gitignore" (точка В НАЧАЛЕ не trailing). name="" → "" не в
        # WINDOWS_RESERVED, не трогаем. Имя сохраняется.
        assert sanitize_filename(".gitignore") == ".gitignore"

    def test_url_like_input(self):
        # Кто-то прислал URL вместо имени — должны вытащить basename
        # https:// — после удаления : и / останется https + filename.pdf
        # basename для "https://example.com/file.pdf" → "file.pdf"
        assert sanitize_filename("https://example.com/file.pdf") == "file.pdf"

    def test_homoglyph_lookalike_kept(self):
        # Кириллическая "а" и латинская "a" — выглядят одинаково,
        # но это разные code points. Мы НЕ нормализуем homoglyph'ы
        # (это сложная отдельная тема, пользователю виднее).
        # Главное — не падать.
        cyrillic_a = "\u0430"  # а
        result = sanitize_filename(f"file{cyrillic_a}.txt")
        assert result == f"file{cyrillic_a}.txt"


# =====================================================================
# Backward compatibility
# =====================================================================


class TestBackwardCompatAlias:
    """slugify_filename — алиас для импортов извне модуля."""

    def test_alias_is_same_function(self):
        # Алиас должен вести на ту же функцию
        assert slugify_filename is sanitize_filename

    def test_alias_works(self):
        assert slugify_filename("Отчёт.pdf") == "Отчёт.pdf"
