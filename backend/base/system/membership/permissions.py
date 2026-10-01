# Copyright 2025 FARA CRM
# Membership permissions.

from dataclasses import dataclass


@dataclass(frozen=True)
class MemberPermissions:
    """
    Права участника — значения is_admin и can_*-полей его записи.

    Общие для всех участников: читать и писать, приглашать и удалять
    участников. Модель со своими can_*-полями наследует класс и добавляет
    их (см. ChatPermissions у чата).
    """

    can_read: bool = True
    can_write: bool = True
    can_invite: bool = False
    can_remove: bool = False
    is_admin: bool = False
