"""Exceptions related to auth"""

from backend.base.system.auth.exception import AuthFailed


class SessionErrorFormat(AuthFailed):
    """Exception on session not sended from client or in wrong format"""


class SessionNotExist(AuthFailed):
    """Exception on session not exist"""


class SessionExpired(AuthFailed):
    """Exception on session expire fail"""


class UserNotExist(AuthFailed):
    """Exception on session not exist"""


class PasswordFailed(AuthFailed):
    """Exception on session not exist"""
