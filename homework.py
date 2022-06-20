import logging
import os
import requests
import sys
import time
import telegram

from dotenv import load_dotenv
from exceptions import HWPrException
from http import HTTPStatus


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PR_TOKEN')
TELEGRAM_TOKEN = os.getenv('TEL_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TEL_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
formatter = '%(asctime)s, %(levelname)s, %(message)s'
handler = logging.StreamHandler(sys.stdout)
logger.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
        logger.info(f'Соообщение отправлено в телеграм: {message}')
    except telegram.error.TelegramError(message):
        logger.error(f'Ошибка работы с телеграм: {message}')


def get_api_answer(current_timestamp):
    """
    Делает запрос на Практикум.Домашка API.
    Dозвращает декодированный ответ json.
    Изменяет размер времени в формате int в качестве параметра.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException:
        message = 'Не удается связаться с конечной точкой.'
        raise HWPrException(message)

    if response.status_code != HTTPStatus.OK:
        message = (f'Конечная точка {ENDPOINT} недоступна, '
                   f'http status: {response.status_code}'
                   )
        raise HWPrException(message)

    return response.json()


def check_response(response):
    """
    Проверяет, содержит ли данный ответ ключ "homeworks".
    Возвращает его значение, если это список.
    """
    if 'homeworks' not in response:
        message = 'В ответе API нет ключа "homeworks"'
        raise TypeError(message)

    hw_list = response['homeworks']

    if not isinstance(hw_list, list):
        message = ('Тип значения "homeworks" в ответе API'
                   f'"{type(hw_list)}" не является списком'
                   )
        raise HWPrException(message)

    return hw_list


def parse_status(homework):
    """
    Берет словарь для домашнего задания.
    Возвращает строку с именем и статусом
    текущего домашнего задания.
    """
    if 'homework_name' in homework:
        homework_name = homework.get('homework_name')
    else:
        message = 'API вернул домашнее задание без ключа "homework_name"'
        raise KeyError(message)
    homework_status = homework.get('status')

    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        message = ('API вернуд'
                   f'неизвестный {homework_status} для "{homework_name}"'
                   )
        raise HWPrException(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """
    Возвращает значение False.
    Если одна из переменных TOKENS или CHAT_ID пуста.
    Возвращает значение True, если PRACTICUM_TOKEN.
    TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не пусты.
    """
    variables = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for variable in variables:

        if not variable:
            logger.critical(
                f'Переменная {variable} не определена. '
                'Бот деактивирован'
            )
            return False

    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_upd_time = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            hw_list = check_response(response)

            for homework in hw_list:
                upd_time = homework.get('date_updated')

                if upd_time != prev_upd_time:
                    prev_upd_time = upd_time
                    message = parse_status(homework)
                    send_message(bot, message)
            current_timestamp = int(time.time())

        except HWPrException as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        except Exception as error:
            logger.exception(error)

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
