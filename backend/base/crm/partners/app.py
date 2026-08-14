from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.contact_type import ContactType, INITIAL_CONTACT_TYPES


class PartnersApp(App):
    """
    App auth
    """

    info = {
        "ui_menu": True,
        "ui_menu_name": "contacts",
        "name": "Partners",
        "summary": "Module allow work with partners",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    # contact_type — конфигурационный справочник, а не пользовательские данные,
    # поэтому обычному пользователю только чтение:
    BASE_USER_ACL = {
        "partner": ACL.FULL,
        "contact": ACL.FULL,
        "contact_type": ACL.READ_ONLY,
    }

    ROLE_ACL = {
        "system_admin": {
            "contact_type": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Начальные типы контактов (в т.ч. новый тип 'sip' для extension)
        for type_data in INITIAL_CONTACT_TYPES:
            existing = await env.models.contact_type.search(
                filter=[("name", "=", type_data["name"])],
            )
            if not existing:
                await env.models.contact_type.create(
                    payload=ContactType(**type_data),
                )

        await self._migration_contact_name_to_value(env)

    async def _migration_contact_name_to_value(self, env: "Environment"):
        """
        МИГРАЦИЯ (временная — УДАЛИТЬ после переноса на всех инсталляциях).

        Рефактор Contact: раньше РЕАЛЬНОЕ значение лежало в поле name; теперь
        оно в value, а name — человекочитаемое описание.

        Шаги (идемпотентно, отрабатывает один раз — гейт по наличию value IS NULL):
          1) КОПИРОВАНИЕ name → value (совместимость): значение раньше лежало в
             name; name НЕ трогаем (остаётся как есть).
          2) Канонизация телефонных контактов к E.164 (вариант A: нормализуем
             и хранимые данные, чтобы матчинг с входящим номером был точным).
        """
        read = env.apps.db.get_session()
        not_migrated = await read.execute(
            "SELECT 1 FROM contact WHERE value IS NULL LIMIT 1"
        )
        if not not_migrated:
            return  # уже мигрировано (или свежая инсталляция без легаси)

        async with env.apps.db.get_transaction() as session:
            # TODO: удалить, нужна только для обратной совместимости
            await session.execute(
                "UPDATE contact SET value = name "
                "WHERE value IS NULL AND name IS NOT NULL"
            )

            # 2) Канонизация телефонных контактов к E.164
            phone_rows = await session.execute("""
                SELECT c.id, c.value
                FROM contact c
                JOIN contact_type ct ON ct.id = c.contact_type_id
                WHERE ct.is_phone_format = true AND c.value IS NOT NULL
                """)
            for row in phone_rows or []:
                canon = env.models.contact._canonicalize(row["value"])
                if canon != row["value"]:
                    await session.execute(
                        "UPDATE contact SET value = %s WHERE id = %s",
                        (canon, row["id"]),
                    )
