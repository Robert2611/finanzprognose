"""Exceptions that carry a machine-readable {code, params} payload for the API layer."""


class ApiError(Exception):
    def __init__(self, code: str, **params):
        self.code = code
        self.params = params
        super().__init__(code)


class NotFound(ApiError):
    pass


class Conflict(ApiError):
    pass
