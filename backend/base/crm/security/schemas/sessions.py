from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from pydantic import BaseModel

from backend.base.system.dotorm.dotorm.fields import Many2one
from backend.base.system.schemas.base_schema import Id

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User

    SchemaUser = User.__schema__


class SchemaSession(BaseModel, extra="forbid"):
    id: Id
    active: bool
    user_id: Annotated["SchemaUser", Many2one]
    token: str
    ttl: int
    expired_datetime: datetime | None

    create_datetime: datetime
    create_user_id: Annotated["SchemaUser", Many2one]
    update_datetime: datetime
    update_user_id: Annotated["SchemaUser", Many2one]
