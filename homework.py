import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telegram.error import TelegramError

from exceptions import (
    APIRequestError,
    HomeworkStatusError,
    MissingTokensError,
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}
API_REQUEST_TIMEOUT = 5

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s, %(levelname)s, %(message)s, %(name)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет наличие обязательных токенов."""
    required_tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    missing_tokens = []

    for token_name, token_value in required_tokens.items():
        if token_value is None:
            missing_tokens.append(token_name)
    if missing_tokens:
        logger.critical(
            "Отсутствуют обязательные токены: %s", ", ".join(missing_tokens)
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Бот отправил сообщение "%s"', message)
        return True
    except TelegramError as error:
        logger.error("Ошибка при отправке сообщения в Telegram: %s", error)
        return False


def get_api_answer(timestamp):
    """Отправляет запрос к API Практикума и получает статус."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=API_REQUEST_TIMEOUT,
        )
        print(response)
        if response.status_code != HTTPStatus.OK:
            error_message = (
                f"Эндпоинт {ENDPOINT} недоступен.\n "
                f"Код ответа API: {response.status_code}.\n "
                f"URL запроса: {response.url}.\n "
                f"Хедеры ответа: {response.headers}.\n "
                f"Текст ответа: {response.text}"
            )
            raise APIRequestError(error_message)
        return response.json()

    except requests.exceptions.RequestException as error:
        raise APIRequestError("Ошибка запроса к API: %s", error)
    except ValueError as error:
        raise APIRequestError("Ошибка декодирования ответа API: %s", error)


def check_response(response):
    """Проверка содержимого ответа API."""
    if not isinstance(response, dict):
        raise TypeError(
            "Ответ API имеет неверный формат: не является словарем"
        )
    if "homeworks" not in response:
        raise KeyError('Отсутствует ожидаемый ключ "homeworks" в ответе API')
    if "current_date" not in response:
        raise KeyError(
            'Отсутствует ожидаемый ключ "current_date" в ответе API'
        )

    homeworks = response.get("homeworks")
    if not isinstance(homeworks, list):
        raise TypeError(
            'Ответ API имеет неверный формат: "homeworks" не является списком'
        )
    return homeworks


def parse_status(homework):
    """Переводит полученный статус в сообщение для отправки в чат."""
    if not isinstance(homework, dict):
        raise HomeworkStatusError(
            "Информация о домашней работе имеет неверный формат"
        )
    if "homework_name" not in homework:
        raise HomeworkStatusError(
            'Отсутствует ключ "homework_name" в информации о домашней работе'
        )
    if "status" not in homework:
        raise HomeworkStatusError(
            'Отсутствует ключ "status" в информации о домашней работе'
        )

    homework_name = homework["homework_name"]
    homework_status = homework["status"]

    if homework_status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusError(
            f"Неожиданный статус домашней работы: {homework_status}"
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise MissingTokensError("Отсутствуют обязательные токены")

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None
    unique_error_messages = set()
    last_status = {}

    while True:
        try:
            api_response = get_api_answer(timestamp)
            homeworks = check_response(api_response)
            if not homeworks:
                logger.debug("Отсутствие в ответе новых статусов")
            else:
                homework = homeworks[0]
                homework_name = homework.get("homework_name")
                homework_status = homework.get("status")
                if (
                    homework_name not in last_status
                    or last_status[homework_name] != homework_status
                ):
                    message = parse_status(homework)
                    send_message(bot, message)
                    last_status[homework_name] = homework_status
            timestamp = api_response.get("current_date", timestamp)
            last_error = None
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
            if str(error) != last_error:
                if str(error) not in unique_error_messages:
                    send_message(bot, message)
                    unique_error_messages.add(str(error))
                last_error = str(error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
