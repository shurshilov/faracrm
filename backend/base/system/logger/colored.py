# Copyright 2025 FARA CRM
# Custom logging formatter with colored [FARA *] tags

import logging

# ANSI
GREEN = "\033[32m"
BLUE = "\033[34m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"

# Tag mapping: logger name prefix → (tag text, color)
# ВАЖНО: более специфичные префиксы должны идти ПЕРВЫМИ
#
# Палитра:
#   SYSTEM (инфраструктура)  → синий   — стабильный фон, не отвлекает
#   CRM    (бизнес-логика)   → зелёный — активность, ключевые события
#   CRON   (фоновые задачи)  → dim yellow — второстепенный, не отвлекает
TAGS = {
    "backend.base.system.cron": ("[FARA CRON]", f"{DIM}{YELLOW}"),
    "backend.base.crm": ("[FARA CRM]", GREEN),
    "backend.base.system": ("[FARA SYSTEM]", BLUE),
    "cron": ("[FARA CRON]", f"{DIM}{YELLOW}"),
}


class FaraFormatter(logging.Formatter):
    """
    Добавляет цветной тег [FARA CRM] / [FARA SYSTEM] / [FARA CRON]
    перед именем логгера. Только тег цветной, остальная строка обычная.
    """

    def format(self, record: logging.LogRecord) -> str:
        tag = ""
        for prefix, (label, color) in TAGS.items():
            if record.name.startswith(prefix):
                tag = f"{color}{label}{RESET} "
                break

        original_name = record.name
        if tag:
            record.name = f"{tag}{record.name}"

        result = super().format(record)
        record.name = original_name
        return result
