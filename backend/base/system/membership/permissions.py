# Copyright 2025 FARA CRM
# Membership permissions.

from dataclasses import dataclass


@dataclass(frozen=True)
class MemberPermissions:
    """
    Набор прав участника — is_admin и can_*-поля его записи. По умолчанию
    набор пуст: включённые права перечисляют явно.

    Набором задают права нового участника (MemberMixin.add) и права, нужные
    для действия (MemberMixin.check_permissions):

        ChatPermissions(can_invite=True)   # ровно одно право

    Общие для всех участников: читать и писать, приглашать и удалять
    участников. Модель со своими can_*-полями наследует класс и добавляет
    их (см. ChatPermissions у чата).
    """

    can_read: bool = False
    can_write: bool = False
    can_invite: bool = False
    can_remove: bool = False
    is_admin: bool = False
