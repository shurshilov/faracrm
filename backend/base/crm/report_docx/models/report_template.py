from backend.base.crm.attachments.models.attachments import Attachment

from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    PolymorphicMany2one,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.schemas.base_schema import Id


class ReportTemplate(DotModel):
    """
    Шаблон отчёта DOCX.

    Хранит ссылку на Attachment с DOCX-файлом (Jinja2-теги).
    model_name — таблица DotORM (напр. "sale").
    python_function — имя @staticmethod на модели, вызывается через getattr.
    """

    __table__ = "report_template"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Report Name")
    active: bool = Boolean(default=True)

    model_name: str = Char(
        string="Model",
        help="DotORM table name, e.g. 'sale', 'partners'",
    )
    python_function: str = Char(
        string="Data Function",
        help="Method name on model class, e.g. 'sale_invoice_rus'",
    )
    template_file: Attachment | None = PolymorphicMany2one(
        relation_table=Attachment,
        string="DOCX Template",
    )
    output_format: str = Selection(
        options=[
            ("docx", "DOCX"),
            ("pdf", "PDF"),
        ],
        default="docx",
        string="Output Format",
    )
    description: str | None = Text(string="Description")
