"""
Реализация AccessChecker для проверки доступа через ACL и Rules.
"""

import json
import re
from typing import TYPE_CHECKING, Any

from backend.base.system.core.enviroment import Environment
from backend.base.system.dotorm.dotorm.access import (
    BYPASS_DOMAIN,
    BYPASS_DOMAIN_LEGACY,
    SUPERUSER,
    AccessChecker,
    Operation,
)
from backend.base.crm.security.models.sessions import (
    SystemSession,
    AnonymousSession,
)
from backend.base.system.dotorm.dotorm.components.filter_parser import (
    SqlFragment,
)
from backend.base.crm.security.rule_operators import (
    resolve_operators,
)

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

    # FARA — политика default-deny: без сессии в контексте CRUD запрещён.
    require_session = True

    def __init__(self, env: Environment):
        self.env = env

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

        # AnonymousSession: разрешён только READ к таблицам, явно
        # перечисленным в session.allowed_tables — список передаётся
        # из public-роутера (см. AuthTokenApp.use_anonymous_session).
        # Принцип минимальных привилегий: каждый роутер декларирует
        # ровно те таблицы которые ему нужны.
        if isinstance(session, AnonymousSession):
            if operation == Operation.READ and model in session.allowed_tables:
                return True, []
            return False, []

        # Конвертируем имя таблицы в имя модели: "users" → "user"
        model = self.env.models._get_model_name_by_table(model)
        user_id = session.user_id.id

        # Роли загружаются ОДИН раз
        role_ids = await self._get_user_roles(user_id)

        # 1. Проверка ACL
        has_acl = await self._check_acl(role_ids, model, operation)
        if not has_acl:
            return False, []

        # Команды — из сессии (гидрируются при сборке, см. _set_team_ids), без
        # запроса. Сюда доходим только для обычной сессии (admin/anonymous
        # отсечены выше), поэтому team_ids уже проставлены. Доступ через точку
        # безопасен: team_ids — реальное поле User (как role_ids ниже в
        # check_field_access), у негидратированной сессии → None → `or []`.
        session_team_ids = [t.id for t in (session.user_id.team_ids or [])]
        domain = await self._get_domains(
            role_ids, model, operation, user_id, team_ids=session_team_ids
        )
        # 2. Проверка Rules (если есть record_ids)
        if record_ids:
            has_rules = await self._check_rules(model, record_ids, domain)
            return has_rules, []

        return True, domain

    async def check_field_access(
        self,
        session: "Session",
        model: str,
        operation: Operation,
        field_names: list[str],
    ) -> list[str]:
        """
        Field-level доступ: какие поля сессия НЕ вправе писать.

        Третья ось доступа (ACL=таблица, Rules=строка, тут=поле). Вызывается
        из ORM write-пути уже после ACL/Rules и только для меняющихся
        role_*-полей (отбор делает ORM). Здесь — только проверка роли.

        Правила role_* трактуются так:
        - токен SUPERUSER → разрешено только is_admin (полный доступ уже
          отсечён выше, значит для остальных — запрет);
        - иначе у пользователя должна быть хотя бы одна из перечисленных
          ролей (по code, с учётом наследования based_role_ids).

        Returns:
            Список запрещённых полей (пустой = всё можно).
        """
        # admin / SystemSession — полный доступ, поля не ограничиваем.
        if self._is_full_access(session):
            return []

        # AnonymousSession не пишет ничего (сюда обычно и не доходит, но
        # на всякий случай запрещаем все кандидаты явно).
        if isinstance(session, AnonymousSession):
            return list(field_names)

        model_name = self.env.models._get_model_name_by_table(model)
        Model = self.env.models._get_model(model_name)
        if Model is None:
            return []

        all_fields = Model.get_fields()
        # Коды ролей берём из самой сессии (кладутся развёрнутыми при
        # сборке/кэшировании сессии — горячий путь без запроса в БД).
        # role_ids может быть None у негидратированных сессий (cookie-auth,
        # внутренний код) → трактуем как «нет ролей»: restricted-поля будут
        # запрещены, но без падения (иначе TypeError на итерации None).
        user_codes = {
            r.code for r in (session.user_id.role_ids or []) if r.code
        }
        denied: list[str] = []

        for name in field_names:
            field = all_fields.get(name)
            if field is None:
                continue
            required = field.required_roles(operation.value)
            if not required:
                continue

            req_codes = set(required) - {SUPERUSER}
            if not req_codes:
                # Поле только для суперпользователя, а мы уже не admin.
                denied.append(name)
                continue

            if not (req_codes & (user_codes or set())):
                denied.append(name)

        return denied

    # =========================================================================
    # Private: базовые проверки
    # =========================================================================

    def system_session(self) -> "SystemSession":
        """
        Сессия для .sudo(). Именно НАША: _is_full_access сверяет тип через
        isinstance, и маркер из dotorm полным доступом признан не будет.
        """
        from backend.base.crm.users.models.users import SYSTEM_USER_ID

        return SystemSession(user_id=SYSTEM_USER_ID)

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

    async def _get_user_team_ids(self, user_id: int) -> list[int]:
        """ID команд пользователя (team_crm.user_ids M2M) — источник
        {{team_ids}}. Прямой SQL (внутри checker нельзя звать ORM — рекурсия).
        Join-таблица team_crm_user_many2many: column1=user_id, column2=team_id.
        """
        db_session = self.env.models.model._get_db_session()
        stmt = "SELECT team_id FROM team_crm_user_many2many WHERE user_id = %s"
        result = await db_session.execute(stmt, [user_id])
        return [row["team_id"] for row in result]

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
        team_ids: list[int] | None = None,
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

        # Команды для {{team_ids}}: обычно приходят из сессии (гидрируются при
        # сборке — без запроса на каждую проверку). Запрос — только fallback
        # для вызовов без сессии (напр. @has_parent_access из rule_operators).
        if team_ids is None:
            team_ids = await self._get_user_team_ids(user_id)

        # Парсим и объединяем domains
        domains = []
        for row in result:
            domain_str = row.get("domain")
            if domain_str:
                try:
                    domain = json.loads(domain_str)
                    # если есть специфичный домен, то тогда сразу разрешить
                    if domain in [BYPASS_DOMAIN, BYPASS_DOMAIN_LEGACY]:
                        return []
                    if domain:
                        # Подставляем переменные ({{user_id}}, {{team_ids}})
                        domain = self._substitute_variables(
                            domain, user_id, team_ids
                        )
                        # Раскрываем кастомные операторы. Может вернуться:
                        # - SqlFragment (если rule был просто @-оператор)
                        # - список triplets/SqlFragment'ов
                        # - обычный domain как был

                        domain = await resolve_operators(
                            domain,
                            user_id,
                            env=self.env,
                            current_model=model,
                        )
                        domains.append(domain)
                except (json.JSONDecodeError, TypeError):
                    continue

        if not domains:
            return []

        if len(domains) == 1:
            d = domains[0]
            # SqlFragment нельзя возвращать как domain — он не list.
            # Оборачиваем в list чтобы FilterParser обработал корректно.
            if isinstance(d, SqlFragment):
                return [d]
            return d

        # Несколько rules — OR-объединение
        combined = []
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

        # Проверяем через search_count.
        check_filter = [("id", "in", record_ids), domain]
        count = await Model.search_count(filter=check_filter)

        return count == len(record_ids)

    # =========================================================================
    # Private: подстановка переменных
    # =========================================================================

    def _substitute_variables(
        self, domain: Any, user_id: int, team_ids: list[int] | None = None
    ) -> Any:
        """
        Рекурсивно подставляет переменные в domain.

        Поддерживаемые переменные:
        - {{user_id}} или {{user.id}} — ID текущего пользователя (скаляр)
        - {{team_ids}} — список ID команд пользователя (team_crm.user_ids)

        ВАЖНО про {{team_ids}}: это ЦЕЛОЗНАЧНАЯ подстановка (возвращаем list),
        а не re.sub по подстроке — regex вернул бы строку, а нам нужен список
        для `("team_id", "in", [..])`. Пустой список нельзя отдавать как []:
        parser собрал бы `IN ()` — синтаксическая ошибка Postgres. Поэтому для
        юзера без команд возвращаем [-1] (гарантированный no-match).
        """
        if isinstance(domain, str):
            if re.fullmatch(r"\s*\{\{\s*team_ids\s*\}\}\s*", domain):
                return list(team_ids) if team_ids else [-1]
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
                self._substitute_variables(item, user_id, team_ids)
                for item in domain
            ]

        elif isinstance(domain, tuple):
            return tuple(
                self._substitute_variables(item, user_id, team_ids)
                for item in domain
            )

        return domain
