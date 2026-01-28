from typing import TYPE_CHECKING, Self
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Many2many,
    Many2one,
    One2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel

if TYPE_CHECKING:
    from .rules import Rule
    from .acls import AccessList
from backend.base.crm.users.models.users import User
from backend.base.system.core.enviroment import env
from .models import Model
from .apps import App


class Role(DotModel):
    """
    Роль пользователя.

    Роль определяет набор прав доступа через:
    - ACL (acl_ids) — права на модели (CRUD)
    - Rules (rule_ids) — фильтрация записей (domain)

    Иерархия через based_role_ids:
    - crm_manager.based_role_ids = [crm_user]
    - Менеджер получает все права crm_user + свои
    """

    __table__ = "roles"

    id: int = Integer(primary_key=True)
    code: str = Char(max_length=64, unique=True)
    name: str = Char(max_length=128)

    # Для группировки в UI
    app_id: App | None = Many2one(relation_table=App)

    # Иерархия ролей — эта роль основана на (расширяет) других
    based_role_ids: list[Self] = Many2many(
        store=False,
        relation_table=lambda: env.models.role,
        many2many_table="role_based_many2many",
        column1="role_id",
        column2="based_role_id",
        default=[],
    )

    # Обратная связь — для какой модели роль (опционально)
    model_id: Model | None = Many2one(relation_table=Model)

    # Связи
    user_ids: list[User] = Many2many(
        store=False,
        relation_table=User,
        many2many_table="user_role_many2many",
        column1="user_id",
        column2="role_id",
        default=[],
        ondelete="cascade",
    )
    acl_ids: list["AccessList"] = One2many(
        store=False,
        relation_table=lambda: env.models.access_list,
        relation_table_field="role_id",
        default=[],
    )
    rule_ids: list["Rule"] = One2many(
        store=False,
        relation_table=lambda: env.models.rule,
        relation_table_field="role_id",
        default=[],
    )

    @classmethod
    async def get_all_roles(cls, role_ids: list[int]) -> list[int]:
        """
        Собирает role_ids + все based_role_ids рекурсивно.

        Использует рекурсивный CTE — один запрос вместо N+1.

        Args:
            role_ids: Начальные ID ролей

        Returns:
            Список ID всех ролей (входные + все based)
        """
        if not role_ids:
            return []

        query = """
            WITH RECURSIVE role_tree AS (
                SELECT unnest($1::int[]) AS role_id
                UNION
                SELECT rb.based_role_id
                FROM role_tree rt
                JOIN role_based_many2many rb ON rb.role_id = rt.role_id
            )
            SELECT DISTINCT role_id FROM role_tree
        """

        session = env.apps.db.get_session()
        result = await session.execute(query, [role_ids], cursor="fetch")
        return [row["role_id"] for row in result]
