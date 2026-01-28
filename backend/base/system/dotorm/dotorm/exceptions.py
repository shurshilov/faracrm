"""Exceptions related to ORM and builder."""


class OrmConfigurationFieldException(Exception):
    """Exception raised when wrong config model or fields."""


class OrmUpdateEmptyParamsException(Exception):
    """Exception raised when ORM doesn't have required params."""
