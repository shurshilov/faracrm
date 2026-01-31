from pydantic import BaseModel

from backend.base.system.schemas.base_schema import Id


class SchemaAttachmentRoute(BaseModel):
    id: Id
    name: str
    model: str | None = None
    is_default: bool = False
