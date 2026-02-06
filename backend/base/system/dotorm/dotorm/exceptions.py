"""Exceptions related to ORM and builder."""


class OrmConfigurationFieldException(Exception):
    """Exception raised when wrong config model or fields."""


class OrmUpdateEmptyParamsException(Exception):
    """Exception raised when ORM doesn't have required params."""


class RecordNotFound(Exception):
    """
    Raised when record is not found but was expected to exist.
    
    Used by get_or_raise() and similar methods where absence is an error.
    """
    
    def __init__(self, model: str, id: int):
        self.model = model
        self.id = id
        super().__init__(f"{model} with id={id} not found")
