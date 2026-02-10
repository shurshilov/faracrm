# Copyright 2025 FARA CRM
# Custom logging formatter with colored [FARA *] tags

import logging

# ANSI
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"

# Tag mapping: logger name prefix → (tag text, color)
TAGS = {
    "backend.base.crm": ("[FARA CRM]", CYAN),
    "backend.base.system": ("[FARA SYSTEM]", GREEN),
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
