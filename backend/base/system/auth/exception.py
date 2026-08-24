"""Exceptions related to auth"""


class AuthFailed(Exception):
    """
    Exception on auth fail.

    clear_cookie — можно ли удалять guard-куку в ответе. Кука ОДНА на браузер и
    общая для всех вкладок, поэтому удалять её позволено, только когда доказано,
    что она принадлежит именно той сессии, которая сейчас умерла. Иначе
    протухшая вкладка гасила бы куку живой сессии (см. обработчик 401 в
    auth_token/app.py).
    """

    def __init__(self, *args, clear_cookie: bool = False) -> None:
        super().__init__(*args)
        self.clear_cookie = clear_cookie
