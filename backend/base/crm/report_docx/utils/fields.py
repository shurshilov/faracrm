"""
Объявление ключей функции данных для конструктора шаблонов.

Функция данных возвращает дикт; какие в нём ключи, снаружи не видно, пока
её не запустишь. Декоратор @report_fields описывает их заранее — конструктор
(модуль report_docx_design) показывает эти ключи в каталоге полей рядом с
полями записи модели, а движок вызывает функцию, если её ключ стоит в
шаблоне. Здесь только метаданные, чтобы модули с функциями данных
(sales_report_docx и др.) не зависели от конструктора.
"""

from typing import Callable


class ReportField:
    """Поле функции данных: подпись и тип (money/date/datetime) для фильтра."""

    def __init__(self, label: str, type: str | None = None):
        self.label = label
        self.type = type


class ReportList:
    """Список функции данных (цикл по строкам): подпись + поля элемента."""

    def __init__(self, label: str, **fields: "str | ReportField"):
        self.label = label
        self.fields = fields


def report_fields(**fields: "str | ReportField | ReportList") -> Callable:
    """Объявить ключи дикта функции данных: по ним конструктор строит
    каталог, а движок решает, вызывать ли функцию.

    @staticmethod
    @report_fields(bik="БИК", summ=ReportField("Сумма", "money"),
                   order_line=ReportList("Позиции", name="Наименование", ...))
    async def sale_invoice_rus(env, record_id): ...

    Ставится ПОД @staticmethod: атрибут вешается на саму функцию, её и
    возвращает getattr(model, name).
    """

    def decorator(func):
        func._report_fields = fields
        return func

    return decorator


def report_params(**labels: str) -> Callable:
    """Подписи аргументов функции данных для формы сводного отчёта
    (превью конструктора, кнопка «Сформировать»). Тип и значение по
    умолчанию форма берёт из сигнатуры; без подписи показывает имя.

    @staticmethod
    @report_fields(...)
    @report_params(days="За сколько дней")
    async def sales_period_data(env, days: int = 30): ...
    """

    def decorator(func):
        func._report_params = labels
        return func

    return decorator
