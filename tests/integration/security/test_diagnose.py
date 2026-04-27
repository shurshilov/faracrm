"""
Quick diagnostic test — выводит состояние БД после conftest seed.
"""

import pytest

pytestmark = pytest.mark.integration


class TestDiagnostic:
    async def test_print_roles_acls_rules(self):
        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.security.models.acls import AccessList
        from backend.base.crm.security.models.rules import Rule
        from backend.base.crm.security.models.models import Model
        from backend.base.crm.users.models.users import User

        roles = await Role.search(fields=["id", "code", "name"])
        print("\n=== Roles ===")
        for r in roles:
            print(f"  {r.code} (id={r.id})")

        # ACL для base_user
        base_user = await Role.search(
            filter=[("code", "=", "base_user")], limit=1
        )
        if base_user:
            acls = await AccessList.search(
                filter=[("role_id", "=", base_user[0].id)],
                fields=[
                    "id",
                    "name",
                    "perm_create",
                    "perm_read",
                    "perm_update",
                    "perm_delete",
                ],
            )
            print(f"\n=== ACL for base_user (count={len(acls)}) ===")
            for acl in acls:
                print(
                    f"  {acl.name}: c={acl.perm_create} "
                    f"r={acl.perm_read} u={acl.perm_update} d={acl.perm_delete}"
                )

        # Rules для интересующих моделей — без точечной нотации
        for model_name in [
            "chat",
            "chat_message",
            "attachment",
            "lead",
            "project",
            "user",
        ]:
            # Найти model_id через models таблицу
            m = await Model.search(
                filter=[("name", "=", model_name)],
                fields=["id"],
                limit=1,
            )
            if not m:
                print(
                    f"\n=== Model '{model_name}' NOT FOUND in models table ==="
                )
                continue
            rules = await Rule.search(
                filter=[("model_id", "=", m[0].id)],
                fields=["id", "name", "perm_read", "role_id"],
            )
            print(f"\n=== Rules for {model_name} (count={len(rules)}) ===")
            for r in rules:
                role_str = f"role_id={r.role_id.id if r.role_id else 'None'}"
                print(f"  {r.name}: read={r.perm_read} {role_str}")

        # Создать тестового user'а с ролью base_user, проверить роли
        if base_user:
            base_role_id = base_user[0].id  # ← int!

            test_user_id = await User.create(
                User(
                    name="Diag user",
                    login="diag_user",
                    is_admin=False,
                    role_ids={"selected": [base_role_id]},
                )
            )
            db = User._get_db_session()
            rows = await db.execute(
                "SELECT user_id, role_id FROM user_role_many2many "
                "WHERE user_id = %s",
                [test_user_id],
            )
            print(f"\n=== Test user 1 (create with int id in selected) ===")
            print(f"  Direct SQL user_role_many2many: {list(rows)}")

            # Альтернатива: создать без role_ids, потом update
            test_user2_id = await User.create(
                User(
                    name="Diag user 2",
                    login="diag_user2",
                    is_admin=False,
                )
            )
            test_user2 = await User.get(test_user2_id)
            await test_user2.update(
                payload=User(
                    role_ids={"selected": [base_role_id]},
                )
            )
            rows2 = await db.execute(
                "SELECT user_id, role_id FROM user_role_many2many "
                "WHERE user_id = %s",
                [test_user2_id],
            )
            print(f"\n=== Test user 2 (create + update with int) ===")
            print(f"  Direct SQL user_role_many2many: {list(rows2)}")

        # Проверка template user из app
        template = await User.search(
            filter=[("login", "=", "default_internal")], limit=1
        )
        if template:
            db = User._get_db_session()
            rows3 = await db.execute(
                "SELECT user_id, role_id FROM user_role_many2many "
                "WHERE user_id = %s",
                [template[0].id],
            )
            print("\n=== Template user (default_internal) roles ===")
            print(f"  user_id = {template[0].id}")
            print(f"  Direct SQL user_role_many2many: {list(rows3)}")

        # Проверка based_role_ids (наследование ролей)
        db = User._get_db_session()
        based_rows = await db.execute(
            "SELECT r.code AS role_code, br.based_role_id, "
            "br_role.code AS based_code "
            "FROM role_based_many2many br "
            "JOIN roles r ON r.id = br.role_id "
            "LEFT JOIN roles br_role ON br_role.id = br.based_role_id"
        )
        print("\n=== Role inheritance (based_roles) ===")
        for row in based_rows:
            print(f"  {row['role_code']} → based on → {row['based_code']}")

        # Какие роли реально получит crm_user через рекурсивный CTE?
        # Имитируем _get_user_roles:
        crm_user_role = await Role.search(
            filter=[("code", "=", "crm_user")], limit=1
        )
        if crm_user_role:
            # Создаём юзера через user_factory путь (create + update)
            test_crm_user = await User.create(
                User(
                    name="CRM test",
                    login="crmtest",
                    is_admin=False,
                )
            )
            test_crm_user_obj = await User.get(test_crm_user)
            await test_crm_user_obj.update(
                payload=User(role_ids={"selected": [crm_user_role[0].id]})
            )

            recursive_roles = await db.execute(
                """
                WITH RECURSIVE user_roles AS (
                    SELECT role_id FROM user_role_many2many WHERE user_id = %s
                    UNION
                    SELECT br.based_role_id
                    FROM user_roles ur
                    JOIN role_based_many2many br ON br.role_id = ur.role_id
                )
                SELECT ur.role_id, r.code FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                """,
                [test_crm_user],
            )
            print(f"\n=== crm_user user gets these roles via CTE ===")
            for row in recursive_roles:
                print(f"  role_id={row['role_id']} code={row['code']}")

        assert True
