"""Exceptions related to environment"""


class FaraException(Exception):
    """Exception on business logic"""


class EnvironmentFailed(Exception):
    """Exception on environment fail"""


class ModulesNotFound(EnvironmentFailed):
    """Exception when any module from the settings is not found"""


class RouterNoValid(EnvironmentFailed):
    """Exception when founded router is not APIRouter instance"""
