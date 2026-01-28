from pydantic import BaseModel
from backend.base.system.schemas.base_schema import Id


class SchemaModel(BaseModel, extra="forbid"):
    id: Id
    name: str
