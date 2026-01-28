from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel


class Uom(DotModel):
    __table__ = "uom"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Uom Name")
