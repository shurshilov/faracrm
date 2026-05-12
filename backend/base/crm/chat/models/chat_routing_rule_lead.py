# Copyright 2025 FARA CRM
# Chat routing rules - lead/operator assignment rules

import logging
import re
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    Many2one,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.leads.models.team_crm import TeamCrm
    from backend.base.crm.users.models.users import User

logger = logging.getLogger(__name__)


class ChatRoutingRuleLead(DotModel):
    """Правила автоматического назначения менеджера по лиду.

    Когда приходит сообщение и формируется лид, система проходит по
    активным правилам в порядке `sequence` и применяет первое подходящее.
    Поле `user_id` правила становится ответственным менеджером лида.

    Пример:
        Если в заголовке объявления есть "ОФД" — назначать на user X.
        Если в тексте сообщения есть "касса" — назначать на user Y.
    """

    __table__ = "chat_routing_rule_lead"

    id: int = Integer(primary_key=True)
    name: str = Char(
        max_length=255, required=True, description="Название правила"
    )
    sequence: int = Integer(default=10, description="Порядок применения")
    active: bool = Boolean(default=True)

    # Если коннектор не задан — правило применяется ко всем коннекторам.
    connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        ondelete="cascade",
        description=(
            "Если коннектор не задан, правило применяется ко всем "
            "коннекторам (глобальное правило)."
        ),
        index=True,
    )

    field_name: str = Selection(
        options=[
            ("item_title", "Item title (advertisement title)"),
            ("message_text", "First message text"),
            ("item_url", "Item URL"),
            ("partner_name", "Partner name"),
        ],
        default="item_title",
        required=True,
        description=(
            "По какому полю проверяется условие. "
            "Item title — заголовок объявления (например для Avito)."
        ),
    )
    condition: str = Selection(
        options=[
            ("icontains", "Contains (case insensitive)"),
            ("contains", "Contains (case sensitive)"),
            ("iequals", "Equals (case insensitive)"),
            ("equals", "Equals (case sensitive)"),
            ("regex", "Matches regex"),
        ],
        default="icontains",
        required=True,
        description="Тип сравнения",
    )
    value: str = Char(
        max_length=500,
        required=True,
        description="Строка/паттерн для сравнения. Например 'ОФД'.",
    )
    user_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        ondelete="restrict",
        description="Менеджер, на которого будет назначен лид при срабатывании правила.",
    )
    team_id: "TeamCrm | None" = Many2one(
        relation_table=lambda: env.models.team_crm,
        ondelete="set null",
        description="Опционально: команда продаж для лида.",
    )
    description: str | None = Text(description="Описание правила")

    def _matches(self, payload: dict) -> bool:
        """Проверка одной записи правила на словарь payload.

        payload — dict со ключами: item_title, message_text, item_url, partner_name.
        Любые значения могут быть None/пустыми — тогда правило не срабатывает.
        """
        target = payload.get(self.field_name) or ""
        if not target or not self.value:
            return False
        try:
            if self.condition == "icontains":
                return self.value.lower() in target.lower()
            if self.condition == "contains":
                return self.value in target
            if self.condition == "iequals":
                return target.lower() == self.value.lower()
            if self.condition == "equals":
                return target == self.value
            if self.condition == "regex":
                return bool(re.search(self.value, target))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Routing rule %s evaluation failed: %s", self.id, exc
            )
            return False
        return False

    @hybridmethod
    async def find_user_for(
        self, connector_id: int | None, payload: dict
    ) -> tuple["User | None", "ChatRoutingRuleLead | None"]:
        """Найти ответственного менеджера для лида по правилам.

        Args:
            connector_id: id записи chat_connector (или None для глобальных).
            payload: dict с ключами item_title, message_text, item_url, partner_name.

        Returns:
            (user, rule) — пара (user, rule) либо (None, None) если правил не найдено.
        """
        filter_conditions: list = [("active", "=", True)]
        if connector_id:
            # Правила этого коннектора + глобальные правила (connector_id IS NULL).
            # Глобальные тянутся как fallback.
            filter_conditions.append(
                [
                    ("connector_id", "=", connector_id),
                    "or",
                    ("connector_id", "=", None),
                ]
            )
        else:
            filter_conditions.append(("connector_id", "=", None))

        rules = await self.search(
            filter=filter_conditions,
            sort="sequence",
            order="ASC",
        )
        for rule in rules:
            if rule._matches(payload):
                logger.info(
                    "Chat routing: rule '%s' matched, assigning to user %s",
                    rule.name,
                    rule.user_id.id if rule.user_id else None,
                )
                return rule.user_id, rule
        return None, None
