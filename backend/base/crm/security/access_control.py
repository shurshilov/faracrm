"""
Реализация AccessChecker для проверки доступа через ACL и Rules.
"""

import json
import re
from typing import TYPE_CHECKING, Any

from backend.base.system.core.enviroment import Environment
from backend.base.system.dotorm.dotorm.access import (
    AccessChecker,
    Operation,
)
from backend.base.crm.security.models.sessions import SystemSession

if TYPE_CHECKING:
    from backend.base.crm.security.models.sessions import Session


class SecurityAccessChecker(AccessChecker["Session"]):
    """
    Реализация AccessChecker через ACL (access_list) и Rules.

    Оптимизация: роли пользователя загружаются один раз и переиспользуются
    для проверки ACL и Rules.

    ВАЖНО: Все запросы внутри checker должны использовать прямой SQL,
    чтобы избежать рекурсии (_check_access → check → search → _check_access).
    """

    def __init__(self, env: Environment):
        self.env = env

    # =========================================================================
    # Public API (вызывается из AccessMixin._check_access)
    # =========================================================================

    # async def check_table_access(
    #     self,
    #     session: "Session",
    #     model: str,
    #     operation: Operation,
    # ) -> bool:
    #     """Проверяет ACL (access_list) — доступ к таблице."""
    #     if self._is_full_access(session):
    #         return True

    #     role_ids = await self._get_user_roles(session.user_id.id)
    #     return await self._check_acl(role_ids, model, operation)

    # async def check_row_access(
    #     self,
    #     session: "Session",
    #     model: str,
    #     operation: Operation,
    #     record_ids: list[int],
    # ) -> bool:
    #     """Проверяет Rules — доступ к записям."""
    #     if self._is_full_access(session):
    #         return True

    #     if not record_ids:
    #         return True

    #     role_ids = await self._get_user_roles(session.user_id.id)
    #     return await self._check_rules(
    #         role_ids, model, operation, record_ids, session.user_id.id
    #     )

    # async def get_domain_filter(
    #     self,
    #     session: "Session",
    #     model: str,
    #     operation: Operation,
    # ) -> list:
    #     """Возвращает domain-фильтр из Rules для search."""
    #     if self._is_full_access(session):
    #         return []

    #     role_ids = await self._get_user_roles(session.user_id.id)
    #     return await self._get_domains(role_ids, model, operation, session.user_id.id)

    # =========================================================================
    # Оптимизированный API (для вызова из _check_access одним блоком)
    # =========================================================================

    async def check_access(
        self,
        session: "Session",
        model: str,
        operation: Operation,
        record_ids: list[int] | None = None,
    ) -> tuple[bool, list]:
        """
        Единая проверка доступа: ACL + Rules за один проход.

        Оптимизация: роли загружаются один раз.

        Args:
            session: Сессия пользователя
            model: Имя модели (таблицы)
            operation: Операция (read/create/update/delete)
            record_ids: ID записей (для проверки Rules)

        Returns:
            (has_access, domain_filter):
            - has_access: True если доступ разрешён
            - domain_filter: фильтр для search (пустой если не нужен)
        """
        if self._is_full_access(session):
            return True, []

        # Конвертируем имя таблицы в имя модели: "users" → "user"
        model = self.env.models._get_model_name_by_table(model)
        user_id = session.user_id.id

        # Роли загружаются ОДИН раз
        role_ids = await self._get_user_roles(user_id)

        # 1. Проверка ACL
        has_acl = await self._check_acl(role_ids, model, operation)
        if not has_acl:
            return False, []

        domain = await self._get_domains(role_ids, model, operation, user_id)
        # 2. Проверка Rules (если есть record_ids)
        if record_ids:
            has_rules = await self._check_rules(model, record_ids, domain)
            return has_rules, []

        return True, domain

    # =========================================================================
    # Private: базовые проверки
    # =========================================================================

    def _is_full_access(self, session: "Session") -> bool:
        """Проверяет, есть ли полный доступ (SystemSession или admin)."""
        if isinstance(session, SystemSession):
            return True
        return session.user_id.is_admin

    async def _get_user_roles(self, user_id: int) -> list[int]:
        """
        Получает все роли пользователя (включая наследуемые).

        Один рекурсивный CTE-запрос.
        """
        db_session = self.env.models.model._get_db_session()

        stmt = """
            WITH RECURSIVE user_roles AS (
                SELECT role_id FROM user_role_many2many WHERE user_id = %s
                UNION
                SELECT br.based_role_id
                FROM user_roles ur
                JOIN role_based_many2many br ON br.role_id = ur.role_id
            )
            SELECT role_id FROM user_roles
        """

        result = await db_session.execute(stmt, [user_id])
        return [row["role_id"] for row in result]

    async def _check_acl(
        self,
        role_ids: list[int],
        model: str,
        operation: Operation,
    ) -> bool:
        """Проверяет ACL по уже загруженным ролям."""
        db_session = self.env.models.model._get_db_session()
        perm_field = f"perm_{operation.value}"

        # Используем ANY вместо CTE — роли уже получены
        stmt = f"""
            SELECT 1 FROM access_list al
            JOIN models m ON al.model_id = m.id
            WHERE m.name = %s
              AND al.active = true
              AND al.{perm_field} = true
              AND (al.role_id = ANY(%s) OR al.role_id IS NULL)
            LIMIT 1
        """

        result = await db_session.execute(stmt, [model, role_ids])
        return len(result) > 0

    async def _get_domains(
        self,
        role_ids: list[int],
        model: str,
        operation: Operation,
        user_id: int,
    ) -> list:
        """Получает и объединяет domain-фильтры из Rules."""
        db_session = self.env.models.model._get_db_session()
        perm_field = f"perm_{operation.value}"

        stmt = f"""
            SELECT r.domain FROM rules r
            JOIN models m ON r.model_id = m.id
            WHERE m.name = %s
              AND r.active = true
              AND r.{perm_field} = true
              AND (r.role_id = ANY(%s) OR r.role_id IS NULL)
        """

        result = await db_session.execute(stmt, [model, role_ids])

        if not result:
            return []

        # Парсим и объединяем domains
        domains = []
        for row in result:
            domain_str = row.get("domain")
            if domain_str:
                try:
                    domain = json.loads(domain_str)
                    if domain:
                        # Подставляем переменные
                        domain = self._substitute_variables(domain, user_id)
                        domains.append(domain)
                except (json.JSONDecodeError, TypeError):
                    continue

        if not domains:
            return []

        if len(domains) == 1:
            return domains[0]

        # Несколько domains — объединяем через OR
        combined: list = []
        for i, domain in enumerate(domains):
            if i > 0:
                combined.append("or")
            combined.append(domain)

        return combined

    async def _check_rules(
        self,
        model: str,
        record_ids: list[int],
        domain: list,
    ) -> bool:
        """Проверяет, что все записи попадают под Rules."""
        # Нет правил — доступ разрешён
        if not domain:
            return True

        # Получаем модель
        Model = getattr(self.env.models, model, None)
        if not Model:
            return True

        # Проверяем через search_count
        check_filter = [("id", "in", record_ids)] + domain
        count = await Model.search_count(filter=check_filter)

        return count == len(record_ids)

    # =========================================================================
    # Private: подстановка переменных
    # =========================================================================

    def _substitute_variables(self, domain: Any, user_id: int) -> Any:
        """
        Рекурсивно подставляет переменные в domain.

        Поддерживаемые переменные:
        - {{user_id}} или {{user.id}} — ID текущего пользователя
        """
        if isinstance(domain, str):
            result = re.sub(
                r"\{\{\s*user_id\s*\}\}|\{\{\s*user\.id\s*\}\}",
                str(user_id),
                domain,
            )
            if result.isdigit():
                return int(result)
            return result

        elif isinstance(domain, list):
            return [
                self._substitute_variables(item, user_id) for item in domain
            ]

        elif isinstance(domain, tuple):
            return tuple(
                self._substitute_variables(item, user_id) for item in domain
            )

        return domain
