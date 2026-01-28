from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.schemas.base_schema import Id


class TeamCrm(DotModel):
    __table__ = "team_crm"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Team Name")
