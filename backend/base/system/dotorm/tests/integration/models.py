"""
Test models for integration tests.

Contains all field types available in DotORM.
"""

from dotorm import (
    DotModel,
    Integer,
    BigInteger,
    SmallInteger,
    Char,
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
from dotorm.components import POSTGRES


# ====================
# Base configuration
# ====================


class BaseModel(DotModel):
    """Base model with PostgreSQL dialect."""

    _dialect = POSTGRES


# ====================
# Simple model for basic field tests
# ====================


class Model(BaseModel):
    """Model registry - stores information about ORM models."""

    __table__ = "models"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=128)


# ====================
# Attachment model
# ====================


class Attachment(BaseModel):
    """File attachment model with all common fields."""

    __table__ = "attachments"

    id: int = Integer(primary_key=True)
    name: str | None = Char(max_length=256)
    res_model: str | None = Char(
        max_length=128,
        string="Resource Model",
    )
    res_field: str | None = Char(
        max_length=64,
        string="Resource Field",
    )
    res_id: int | None = Integer(string="Resource ID")
    public: bool | None = Boolean(string="Is public document")
    folder: bool | None = Boolean(string="Is folder")
    access_token: str | None = Char(max_length=64, string="Access Token")
    size: int | None = Integer(string="File Size")
    checksum: str | None = Char(string="Checksum/SHA1", max_length=40)
    mimetype: str | None = Char(max_length=128, string="Mime Type")
    storage_file_id: str | None = Char(
        max_length=256,
        string="Storage file ID",
    )
    storage_parent_id: str | None = Char(
        max_length=256,
        string="Storage file parent ID",
    )
    storage_parent_name: str | None = Char(
        max_length=256,
        string="Storage file parent Name",
    )
    storage_file_url: str | None = Char(
        max_length=512,
        string="Storage file url",
    )


# ====================
# Access control models
# ====================


class AccessList(BaseModel):
    """Access control list - permissions for roles."""

    __table__ = "access_list"

    id: int = Integer(primary_key=True)
    active: bool = Boolean(default=False)
    name: str = Char(max_length=128)
    model_id: "Model | None" = Many2one(relation_table=Model)
    role_id: "Role | None" = Many2one(relation_table=lambda: Role)
    perm_create: bool = Boolean(default=False)
    perm_read: bool = Boolean(default=False)
    perm_update: bool = Boolean(default=False)
    perm_delete: bool = Boolean(default=False)


class Role(BaseModel):
    """User role model."""

    __table__ = "roles"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=64)
    model_id: Model | None = Many2one(relation_table=Model)
    # Many2many: Role <-> User
    user_ids: list["User"] = Many2many(
        store=False,
        relation_table=lambda: User,
        many2many_table="user_role_many2many",
        column1="user_id",
        column2="role_id",
        default=[],
        ondelete="cascade",
    )
    # One2many: Role -> AccessList
    acl_ids: list[AccessList] = One2many(
        store=False,
        relation_table=lambda: AccessList,
        relation_table_field="role_id",
        default=[],
    )


# ====================
# User model with all relation types
# ====================


class User(BaseModel):
    """User model with all field types."""

    __table__ = "users"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=128)
    login: str | None = Char(max_length=64)
    email: str = Char(max_length=256)
    password_hash: str = Char(max_length=256)
    password_salt: str = Char(max_length=256)

    # PolymorphicMany2one: single attachment
    image: Attachment | None = PolymorphicMany2one(relation_table=Attachment)

    # PolymorphicOne2many: multiple attachments
    image_ids: list[Attachment] = PolymorphicOne2many(
        store=False,
        relation_table=Attachment,
        relation_table_field="res_id",
        default=None,
    )

    # Many2many: User <-> Role
    role_ids: list[Role] = Many2many(
        store=False,
        relation_table=lambda: Role,
        many2many_table="user_role_many2many",
        column1="role_id",
        column2="user_id",
        ondelete="cascade",
    )


# ====================
# Model with all basic field types
# ====================


class AllFieldTypes(BaseModel):
    """Model demonstrating all available field types."""

    __table__ = "all_field_types"

    # Primary key
    id: int = Integer(primary_key=True)

    # Integer types
    int_field: int | None = Integer()
    bigint_field: int | None = BigInteger()
    smallint_field: int | None = SmallInteger()

    # String types
    char_field: str | None = Char(max_length=100)
    char_unlimited: str | None = Char()
    text_field: str | None = Text()

    # Boolean
    bool_field: bool | None = Boolean()
    bool_default_true: bool = Boolean(default=True)
    bool_default_false: bool = Boolean(default=False)

    # Numeric types
    decimal_field: "Decimal | None" = Decimal(max_digits=10, decimal_places=2)
    float_field: float | None = Float()

    # Date/Time types
    datetime_field: "Datetime | None" = Datetime()
    date_field: "Date | None" = Date()
    time_field: "Time | None" = Time()

    # Complex types
    json_field: dict | list | None = JSONField()
    binary_field: bytes | None = Binary()


# ====================
# Model for One2one relation test
# ====================


class UserProfile(BaseModel):
    """User profile - One2one relation with User."""

    __table__ = "user_profiles"

    id: int = Integer(primary_key=True)
    user_id: User | None = Many2one(relation_table=User)
    bio: str | None = Text()
    website: str | None = Char(max_length=256)
    phone: str | None = Char(max_length=32)


# ====================
# Model with unique and indexed fields
# ====================


class UniqueModel(BaseModel):
    """Model with unique and indexed fields."""

    __table__ = "unique_models"

    id: int = Integer(primary_key=True)
    code: str = Char(max_length=32, unique=True)
    name: str = Char(max_length=128)
    # indexed field
    category: str | None = Char(max_length=64, index=True)


# ====================
# Model with required fields
# ====================


class RequiredFieldsModel(BaseModel):
    """Model with required (NOT NULL) fields."""

    __table__ = "required_fields"

    id: int = Integer(primary_key=True)
    required_char: str = Char(max_length=100, required=True)
    required_int: int = Integer(required=True)
    optional_char: str | None = Char(max_length=100)


# ====================
# Model with default values
# ====================


class DefaultValuesModel(BaseModel):
    """Model with various default values."""

    __table__ = "default_values"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=100)
    status: str = Char(max_length=32, default="draft")
    active: bool = Boolean(default=True)
    counter: int = Integer(default=0)
    priority: int = Integer(default=10)


# ====================
# List of all models for table creation
# ====================

ALL_MODELS = [
    Model,
    Attachment,
    AccessList,
    Role,
    User,
    AllFieldTypes,
    UserProfile,
    UniqueModel,
    RequiredFieldsModel,
    DefaultValuesModel,
]


# ====================
# Order for creation (respecting foreign keys)
# ====================

MODELS_CREATION_ORDER = [
    Model,  # No dependencies
    Attachment,  # No dependencies
    Role,  # Depends on Model
    User,  # Depends on Attachment
    AccessList,  # Depends on Model, Role
    AllFieldTypes,  # No dependencies
    UserProfile,  # Depends on User
    UniqueModel,  # No dependencies
    RequiredFieldsModel,  # No dependencies
    DefaultValuesModel,  # No dependencies
]
