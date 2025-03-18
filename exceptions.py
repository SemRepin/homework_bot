class APIRequestError(Exception):
    """Исключение при ошибке запроса к API."""
    pass


class HomeworkStatusError(Exception):
    """Исключение при ошибке получения статуса домашней работы."""
    pass
