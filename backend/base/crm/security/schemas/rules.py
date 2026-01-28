# from typing import Annotated
# from pydantic import BaseModel

# from backend.base.system.dotorm.dotorm.fields import Many2one

# from .roles import SchemaRole
# from backend.base.system.schemas.base_schema import Id


# class SchemaRule(BaseModel, extra="forbid"):
#     id: Id
#     name: str
#     role_id: Annotated[SchemaRole | None, Many2one]
