"""
DotORM v2
"""

# Fields
from .fields import (
    Field,
    Integer,
    BigInteger,
    SmallInteger,
    Char,
    Selection,
    Text,
    Boolean,
    Decimal,
    Datetime,
    Date,
    Time,
    Float,
    JSONField,
    Binary,
    Many2one,
    One2many,
    Many2many,
    One2one,
    PolymorphicMany2one,
    PolymorphicOne2many,
)

# Model
from .model import DotModel
from .model import Model, JsonMode

# Components
from .components import (
    Dialect,
    POSTGRES,
    MYSQL,
    FilterParser,
    FilterExpression,
)

# Exceptions
from .exceptions import (
    OrmConfigurationFieldException,
    RecordNotFound,
)

# Access control (permissive by default; opt-in default-deny via a checker
# with require_session=True)
from .access import (
    Operation,
    AccessChecker,
    AccessDenied,
    SystemSession,
    AnonymousSession,
    set_access_session,
    get_access_session,
    clear_access_session,
    set_access_checker,
    get_access_checker,
    is_sudo,
)

__version__ = "2.3.0"

__all__ = [
    # Fields
    "Field",
    "Integer",
    "BigInteger",
    "SmallInteger",
    "Char",
    "Selection",
    "Text",
    "Boolean",
    "Decimal",
    "Datetime",
    "Date",
    "Time",
    "Float",
    "JSONField",
    "Binary",
    "Many2one",
    "One2many",
    "Many2many",
    "One2one",
    "PolymorphicMany2one",
    "PolymorphicOne2many",
    # Model
    "DotModel",
    "Model",
    "JsonMode",
    # Components
    "Dialect",
    "POSTGRES",
    "MYSQL",
    "FilterParser",
    "FilterExpression",
    # Exceptions
    "OrmConfigurationFieldException",
    "RecordNotFound",
    # Access control
    "Operation",
    "AccessChecker",
    "AccessDenied",
    "SystemSession",
    "AnonymousSession",
    "set_access_session",
    "get_access_session",
    "clear_access_session",
    "set_access_checker",
    "get_access_checker",
    "is_sudo",
]
