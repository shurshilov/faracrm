from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel

# from backend.base.system.core.enviroment import env


class Tax(DotModel):
    __table__ = "tax"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Tax Name")
