"""
Движок отчётов report_docx без БД: песочница Jinja и правило «кто
администратор отчётов».

Шаблон отчёта — данные из базы (и присланный конструктором DOCX), а не код
проекта, поэтому выражения в нём не должны доставать внутренности Python
({{ ''.__class__... }} → выполнение команд на сервере). Пустое значение
печатается пустой строкой, фильтры денег/дат работают в песочнице.

Run: pytest tests/unit/test_report_docx_engine.py -v
"""

import io
from types import SimpleNamespace

import pytest

docx = pytest.importorskip("docx")
jinja2 = pytest.importorskip("jinja2")
pytest.importorskip("docxtpl")

from jinja2.exceptions import SecurityError  # noqa: E402

from backend.base.crm.report_docx.routers.reports import (  # noqa: E402
    is_template_admin,
)
from backend.base.crm.report_docx.utils.engine import (  # noqa: E402
    DocxReportEngine,
)


def _docx(*paragraphs: str) -> bytes:
    """DOCX из абзацев (python-docx) — как шаблон, загруженный админом."""
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _text(docx_bytes: bytes) -> list[str]:
    return [p.text for p in docx.Document(io.BytesIO(docx_bytes)).paragraphs]


# ---------------------------------------------------------------------------
# Песочница
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression",
    [
        "{{ ''.__class__.__mro__ }}",
        "{{ cycler.__init__.__globals__ }}",
        "{{ items.__class__.__base__ }}",
        "{{ name.__class__.__subclasses__() }}",
    ],
)
def test_render_rejects_python_internals(expression):
    """Дандер-атрибуты — классический путь SSTI к os/subprocess: песочница
    отдаёт вместо них «unsafe undefined», и шаг дальше по цепочке — ошибка."""
    with pytest.raises(SecurityError):
        DocxReportEngine.render(
            _docx(expression), {"name": "x", "items": [1, 2]}
        )


def test_render_unsafe_attribute_prints_nothing():
    """Одиночный дандер без цепочки — пустая строка, а не имя класса."""
    rendered = DocxReportEngine.render(
        _docx("[{{ name.__class__ }}]", "[{{ items.__len__ }}]"),
        {"name": "x", "items": [1, 2]},
    )
    assert _text(rendered)[:2] == ["[]", "[]"]


def test_render_plain_tags_and_filters():
    """Обычные теги, фильтры и вложенные дикты в песочнице работают."""
    rendered = DocxReportEngine.render(
        _docx(
            "Клиент: {{ partner.name }}",
            "Сумма: {{ amount|money }} от {{ date|date }}",
            "{% for line in lines %}[{{ line.qty }}]{% endfor %}",
        ),
        {
            "partner": {"name": "ООО «Ромашка»"},
            "amount": 1234567.8,
            "date": "2026-09-30",
            "lines": [{"qty": 1}, {"qty": 2}],
        },
    )
    assert _text(rendered)[:3] == [
        "Клиент: ООО «Ромашка»",
        "Сумма: 1 234 567,80 от 30.09.2026",
        "[1][2]",
    ]


def test_render_none_prints_empty_string():
    """Незаполненное поле — пустое место, а не слово «None»."""
    rendered = DocxReportEngine.render(
        _docx("A{{ notes }}B", "C{{ partner.notes }}D"),
        {"notes": None, "partner": {"notes": None}},
    )
    assert _text(rendered)[:2] == ["AB", "CD"]


# ---------------------------------------------------------------------------
# Администратор отчётов (превью, каталог полей, движок PDF)
# ---------------------------------------------------------------------------


def _user(is_admin=False, roles=()):
    return SimpleNamespace(
        is_admin=is_admin,
        role_ids=[SimpleNamespace(code=code) for code in roles],
    )


@pytest.mark.parametrize(
    "user, expected",
    [
        (_user(is_admin=True), True),
        (_user(roles=["system_admin"]), True),
        (_user(roles=["base_user", "system_admin"]), True),
        (_user(roles=["base_user"]), False),
        (_user(), False),
        (SimpleNamespace(is_admin=False, role_ids=None), False),
    ],
)
def test_is_template_admin(user, expected):
    assert is_template_admin(user) is expected
