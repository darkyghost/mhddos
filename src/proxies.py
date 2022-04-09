import time

import requests

from PyRoxy import ProxyUtiles
from .core import logger, cl, PROXIES_URL
from .load_proxies import _O0O00000O0OOOOOO0
from .system import read_or_fetch


def update_proxies(proxies_file):
    if proxies_file:
        content = read_or_fetch(proxies_file)
        if content is None:
            logger.error(f'{cl.RED}Не вдалося зчитати проксі з {proxies_file}{cl.RESET}')
            exit()
        proxies = ProxyUtiles.parseAll([prox for prox in content.split()])
        if not proxies:
            logger.error(f'{cl.RED}У {proxies_file} не знайдено проксі - перевірте формат{cl.RESET}')
            exit()

        logger.info(f'{cl.YELLOW}Зчитано {cl.BLUE}{len(proxies)}{cl.YELLOW} проксі{cl.RESET}')
        return proxies

    logger.info(f'{cl.MAGENTA}Увага, зміни! Можливе зниження трафіку, в обмін на збільшення загальної кількості IP, що атакують{cl.RESET}')
    logger.info(f'{cl.YELLOW}Завантажуємо список проксі...{cl.RESET}')
    raw = requests.get(PROXIES_URL, timeout=20).content
    try:
        working_proxies = ProxyUtiles.parseAll(_O0O00000O0OOOOOO0(raw))
    except Exception:
        working_proxies = []
    if not working_proxies:
        logger.error(f'{cl.RED}Не знайдено робочих проксі - спробуйте трохи згодом{cl.RESET}')
        exit()

    logger.info(f'{cl.YELLOW}Отримано добірку {cl.BLUE}{len(working_proxies):,}{cl.YELLOW} проксі{cl.RESET}')
    return working_proxies
