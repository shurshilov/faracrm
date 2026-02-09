"""Этот файл содержит общие типы. Type alises."""

import re
from enum import IntEnum
from typing import Annotated
from annotated_types import Len
from pydantic import (
    AfterValidator,
    Field,
    UrlConstraints,
)
from pydantic_core import Url


class Language(IntEnum):
    # TODO: заменить накапслок
    English = 1
    Russian = 2


class IntBool(IntEnum):
    FALSE = 0
    TRUE = 1


Id = Annotated[int, Field(ge=1, le=4294967295)]
Limit = Annotated[int, Field(ge=1, le=999)]
OrderId = Annotated[
    str, Field(pattern=r"^(id) (DESC|ASC)$", min_length=6, max_length=7)
]
Secret = Annotated[
    str, Field(pattern=r"^[2-7A-Z]+$", min_length=32, max_length=32)
]
Port = Annotated[int, Field(ge=0, le=65535)]
PositiveInt0 = Annotated[int, Field(ge=0)]
PositiveInt1 = Annotated[int, Field(ge=1)]
ArrayOfInt = Annotated[list[PositiveInt1], Len(min_length=1)]
ArrayOfId500Item = Annotated[list[Id], Len(min_length=1, max_length=500)]
ArrayOfId1000Item = Annotated[list[Id], Len(min_length=1, max_length=1000)]
ArrayOfIdNotEmpty = Annotated[list[Id], Len(min_length=1)]
ArrayOfId = list[Id]
HttpsURL = Annotated[
    Url, UrlConstraints(allowed_schemes=["http", "https"], max_length=2048)
]


def text_file_match(p: str) -> str:
    """Защита от пользовательского ввода, который будет добавлен в файл"""
    if len(p) > 500:
        raise ValueError("Text should be less than 500 chars")

    denied_chars = re.compile(r"^(?=.*[@\-\=\+\r\t]).*$")
    denied_chars_unicode = re.compile(
        r"[\u002B\u002D\u003D\u0040\u2B7E\u240D\u000D\u23CE\u2B90\u2B91]+"
    )
    if p and denied_chars.match(p):
        raise ValueError(
            "Text must not contain prohibited characters, [=,-,+,@,tab,carriage return]"
        )
    if p and denied_chars_unicode.match(p):
        raise ValueError(
            "Text must not contain prohibited characters unicode, [=,-,+,@,tab,carriage return]"
        )
    return p


TextFile = Annotated[
    str, AfterValidator(text_file_match), Field(max_length=500)
]


def regex_password(p: str) -> str:
    """Минимальные требования к паролю,
    для того чтобы пользователи не вводили слабые пароли"""
    re_for_pw: re.Pattern[str] = re.compile(
        r"^(?=.*[A-ZА-Я])(?=.*[a-zа-я])(?=.*[0-9])(?=.*[!@#%&_\"';:<>\-\=\$\^\*\(\)\+\?]).*$"
    )
    if p and not re_for_pw.match(p):
        raise ValueError("Invalid password")
    return p


Password = Annotated[str, AfterValidator(regex_password), Field(min_length=8)]
