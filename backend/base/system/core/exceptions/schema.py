"""
Schemas for exceptions.
"""

from pydantic import BaseModel


class InternalErrorSchema(BaseModel):
    type: str
    message: str


class BusinessErrorSchema(BaseModel):
    code: int
    message: str


class NotFoundErrorSchema(BaseModel):
    code: int
    message: str


class HTTPExceptionSchema(BaseModel):
    detail: str
