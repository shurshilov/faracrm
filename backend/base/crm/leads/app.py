from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.dotorm.dotorm.access import BYPASS_DOMAIN
from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from backend.base.crm.security.utils import init_module_roles
from .models.lead_stage import LeadStage, INITIAL_LEAD_STAGES


class LeadsApp(App):
    """
    App for leads/CRM management.

    Роли:
    ┌──────────────┬─────────────────────────────────────────────────────┐
    │ Код роли     │ Описание                                            │
    ├──────────────┼─────────────────────────────────────────────────────┤
    │ crm_user     │ Пользователь — видит только свои лиды + общие       │
    │              │ (где user_id не задан)                              │
    │ crm_manager  │ Менеджер — видит все лиды                           │
    │ crm_admin    │ Администратор — полный доступ + управление стадиями │
    └──────────────┴─────────────────────────────────────────────────────┘
    """

    info = {
        "ui_menu": True,
        "ui_menu_name": "crm",
        "name": "Leads",
        "summary": "Module allow work with leads",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security", "users"],
    }

    BASE_USER_ACL = {
        "lead_stage": ACL.READ_ONLY,
        "team_crm": ACL.READ_ONLY,
    }

    ROLE_ACL = {
        "crm_user": {
            "lead": ACL.FULL,
            "lead_stage": ACL.READ_ONLY,
            "team_crm": ACL.READ_ONLY,
        },
        "crm_manager": {
            "lead": ACL.FULL,
            "lead_stage": ACL.READ_ONLY,
            "team_crm": ACL.READ_ONLY,
        },
        "crm_admin": {
            "lead": ACL.FULL,
            "lead_stage": ACL.FULL,
            "team_crm": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Роли модуля
        await init_module_roles(
            env,
            "leads",
            [
                ("crm_user", "CRM: пользователь"),
                ("crm_manager", "CRM: менеджер"),
                ("crm_admin", "CRM: администратор"),
            ],
        )

        existing_stages = await env.models.lead_stage.search(
            fields=["id"], limit=1
        )
        if not existing_stages:
            for stage_data in INITIAL_LEAD_STAGES:
                await env.models.lead_stage.create(
                    payload=LeadStage(**stage_data),
                )

        # ACL уже создан через super().post_init(app) (BASE_USER_ACL / ROLE_ACL).
        # Осталось создать row-level rules.
        await self._init_lead_rules(env)

        # Дефолтная команда + авто-заполнение внутренними пользователями.
        await self._init_default_team(env)

    async def _init_default_team(self, env: "Environment"):
        """Создать дефолтную команду и добавить в неё «внутренних
        пользователей» (носителей роли base_user, с учётом наследования — её
        имеют все внутренние роли). Идемпотентно: команда по имени, состав —
        union с текущим (только добавляем, сессии участников инвалидируются
        через team_crm.update → publish_roles_changed). Плюс backfill:
        коннекторы без команды → дефолтная (чтобы новые внешние чаты попадали
        в team-scoped видимость). Системный юзер исключён.
        """
        from backend.base.crm.leads.models.team_crm import TeamCrm
        from backend.base.crm.users.models.users import SYSTEM_USER_ID

        TEAM_NAME = "Команда по умолчанию"

        existing = await env.models.team_crm.search(
            filter=[("name", "=", TEAM_NAME)], fields=["id"], limit=1
        )
        team_id = (
            existing[0].id
            if existing
            else await env.models.team_crm.create(
                payload=TeamCrm(name=TEAM_NAME)
            )
        )

        role = await env.models.role.search(
            filter=[("code", "=", "base_user")], fields=["id"], limit=1
        )
        if not role:
            return

        db = env.models.team_crm._get_db_session()
        # base_user наследуется всеми внутренними ролями → берём носителей всех
        # ролей, которые его наследуют (обход role_based_many2many вверх).
        rows = await db.execute(
            """
            WITH RECURSIVE inheritors AS (
                SELECT $1::int AS role_id
                UNION
                SELECT rb.role_id FROM inheritors i
                JOIN role_based_many2many rb
                  ON rb.based_role_id = i.role_id
            )
            SELECT DISTINCT ur.user_id
            FROM inheritors inh
            JOIN user_role_many2many ur ON ur.role_id = inh.role_id
            WHERE ur.user_id != $2
            """,
            [role[0].id, SYSTEM_USER_ID],
            cursor="fetch",
        )
        member_ids = {r["user_id"] for r in rows}

        cur = await db.execute(
            "SELECT user_id FROM team_crm_user_many2many WHERE team_id = $1",
            [team_id],
            cursor="fetch",
        )
        current = {r["user_id"] for r in cur}
        selected = sorted(current | member_ids)
        if selected != sorted(current):
            team = await env.models.team_crm.get(team_id)
            await team.update(payload=TeamCrm(user_ids={"selected": selected}))

        # Backfill: коннекторы без команды → дефолтная.
        null_conns = await env.models.chat_connector.search(
            filter=[("team_id", "=", None)], fields=["id"]
        )
        for c in null_conns:
            conn = await env.models.chat_connector.get(c.id)
            await conn.update(
                payload=env.models.chat_connector(
                    team_id=env.models.team_crm(id=team_id)
                )
            )

    async def _init_lead_rules(self, env: "Environment"):
        """
        Row-level security для лидов.

        - crm_user:     видит/правит только свои (user_id = я) ИЛИ общие (user_id = None)
        - crm_manager:  видит/правит все лиды
        - crm_admin:    видит/правит все лиды
        """
        from backend.base.crm.security.models.rules import Rule

        lead_model = await env.models.model.search(
            filter=[("name", "=", "lead")], limit=1
        )
        if not lead_model:
            return
        lead_model_rec = lead_model[0]

        role_user = await env.models.role.search(
            filter=[("code", "=", "crm_user")], limit=1
        )
        role_manager = await env.models.role.search(
            filter=[("code", "=", "crm_manager")], limit=1
        )
        role_admin = await env.models.role.search(
            filter=[("code", "=", "crm_admin")], limit=1
        )
        if not role_user or not role_manager or not role_admin:
            return

        rules_to_create = [
            {
                "name": "Лиды: только свои или общие",
                "model_id": lead_model_rec,
                "role_id": role_user[0],
                "domain": [
                    ["user_id", "=", "{{user_id}}"],
                    "or",
                    ["user_id", "=", None],
                ],
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Лиды: все (менеджер)",
                "model_id": lead_model_rec,
                "role_id": role_manager[0],
                "domain": BYPASS_DOMAIN,
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Лиды: все (админ)",
                "model_id": lead_model_rec,
                "role_id": role_admin[0],
                "domain": BYPASS_DOMAIN,
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
        ]

        for rule_data in rules_to_create:
            existing = await env.models.rule.search(
                filter=[("name", "=", rule_data["name"])],
                limit=1,
            )
            if existing:
                continue

            await env.models.rule.create(
                payload=Rule(
                    name=rule_data["name"],
                    active=True,
                    model_id=rule_data["model_id"],
                    role_id=rule_data["role_id"],
                    domain=rule_data["domain"],
                    perm_create=rule_data["perm_create"],
                    perm_read=rule_data["perm_read"],
                    perm_update=rule_data["perm_update"],
                    perm_delete=rule_data["perm_delete"],
                )
            )
