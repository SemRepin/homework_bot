class APIRequestError(Exception):
    """Исключение при ошибке запроса к API."""


class HomeworkStatusError(Exception):
    """Исключение при ошибке получения статуса домашней работы."""


class MissingTokensError(Exception):
    """Исключение при отсутствии обязательных токенов."""
