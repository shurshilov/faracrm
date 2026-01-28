from backend.base.system.dotorm.dotorm.fields import Char, Integer
from backend.base.system.dotorm.dotorm.model import DotModel


class Model(DotModel):
    __table__ = "models"

    id: int = Integer(primary_key=True)
    name: str = Char()

    # acl_ids: list[AccessList] = One2many(
    #     store=False, relation_table=AccessList, relation_table_field="model_id"
    # )

    # role_ids: list[Role] = One2many(
    #     store=False, relation_table=Role, relation_table_field="model_id"
    # )
