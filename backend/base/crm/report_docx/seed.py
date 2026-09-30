"""
Сидер шаблонов-образцов: модуль объявляет список спецификаций (имя, модель,
функция данных, тип, формат, файл DOCX) и при старте получает записи
report_template с привязанными файлами — руками ничего создавать не нужно.

Идемпотентно по имени: удалённый образец вернётся после рестарта,
переименованный — останется. Ошибка одного образца (нет файла, не настроено
хранилище) не роняет старт: шаблон остаётся без файла, админ загрузит его.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

DOCX_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


async def seed_report_templates(
    env: "Environment", specs: list[dict]
) -> dict[str, int]:
    """Создать недостающие шаблоны из specs. Возвращает {имя: id} для всех.

    spec: name, description, model_name, python_function (опц.), report_type
    (record|summary), output_format (docx|pdf), file (Path к DOCX).
    Файл привязывается тем же путём, что и в форме: update полиморфного
    поля template_file словарём с content — ORM создаёт вложение сам.
    """
    templates = env.models.report_template
    ids: dict[str, int] = {}
    for spec in specs:
        name = spec["name"]
        existing = await templates.search_one(
            filter=[("name", "=", name)], fields=["id"]
        )
        if existing:
            ids[name] = existing.id
            continue
        values = {key: value for key, value in spec.items() if key != "file"}
        template_id = await templates.create(templates(**values))
        ids[name] = template_id
        path: Path = spec["file"]
        try:
            content = path.read_bytes()
            template = await templates.search_one(
                filter=[("id", "=", template_id)], fields=["id"]
            )
            await template.update(
                templates(
                    template_file={
                        "name": path.name,
                        "mimetype": DOCX_MIMETYPE,
                        "size": len(content),
                        "res_model": "report_template",
                        "content": content,
                    }
                ),
                fields=["template_file"],
            )
        except Exception as e:
            logger.warning(
                "Sample template %r created without file: %s", name, e
            )
        logger.info(
            "Seeded sample report template %r (id=%s)", name, template_id
        )
    return ids
