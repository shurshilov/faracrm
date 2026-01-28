from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Many2one,
    Boolean,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from .models import Model
from .roles import Role


class AccessList(DotModel):
    __table__ = "access_list"

    id: int = Integer(primary_key=True)
    active: bool = Boolean(default=False)
    name: str = Char()
    model_id: Model | None = Many2one(relation_table=Model)
    role_id: Role | None = Many2one(relation_table=Role)

    perm_create: bool = Boolean(default=False)
    perm_read: bool = Boolean(default=False)
    perm_update: bool = Boolean(default=False)
    perm_delete: bool = Boolean(default=False)

    # def check():
    #     assert mode in ('read', 'write', 'create', 'unlink'), 'Invalid access mode'

    #     self.flush_model()
    #     self.env.cr.execute(f"""
    #         SELECT m.model
    #           FROM access_list a
    #           JOIN model m ON (m.id = a.model_id)
    #          WHERE a.perm_{mode}
    #            AND a.active
    #            AND (
    #                 a.role_id IS NULL OR
    #                 -- use subselect fo force a better query plan. See #99695 --
    #                 a.role_id IN (
    #                     SELECT ur.role_id
    #                         FROM user_role_many2many ur
    #                         WHERE ur.user_id = %s
    #                 )
    #             )
    #         GROUP BY m.model
    #     """, (self.env.uid,))
