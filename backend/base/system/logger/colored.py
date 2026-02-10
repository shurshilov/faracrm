"""
Colored log formatters for FARA CRM.

Purple (magenta) - backend.base.system
Cyan (blue)      - backend.base.crm
"""

import logging


class ColoredFormatter(logging.Formatter):
    """Base colored formatter with ANSI escape codes."""

    COLOR = ""
    RESET = "\033[0m"

    # Level-specific colors (bold for WARNING+)
    LEVEL_COLORS = {
        "WARNING": "\033[1;33m",  # bold yellow
        "ERROR": "\033[1;31m",  # bold red
        "CRITICAL": "\033[1;41m",  # bold red bg
    }

    def format(self, record):
        msg = super().format(record)

        # For WARNING+ use level color instead
        level_color = self.LEVEL_COLORS.get(record.levelname)
        if level_color:
            return f"{level_color}{msg}{self.RESET}"

        if self.COLOR:
            return f"{self.COLOR}{msg}{self.RESET}"

        return msg


class PurpleFormatter(ColoredFormatter):
    """Magenta/purple for backend.base.system modules."""

    COLOR = "\x1b[32m"
    # COLOR = "\033[35m"


class CyanFormatter(ColoredFormatter):
    """Cyan/blue for backend.base.crm modules."""

    COLOR = "\033[36m"
