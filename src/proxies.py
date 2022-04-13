from PyRoxy import ProxyUtiles
from .core import logger, cl, PROXIES_URL
from .system import read_or_fetch, fetch


# @formatter:off
_globals_before = set(globals().keys()).union({'_globals_before'})
# noinspection PyUnresolvedReferences
from .load_proxies import *
decrypt_proxies = globals()[set(globals().keys()).difference(_globals_before).pop()]
# @formatter:on


def update_proxies(proxies_file, previous_proxies):
    if proxies_file:
        proxies = load_provided_proxies(proxies_file)
    else:
        proxies = load_system_proxies()

    if not proxies:
        if previous_proxies:
            proxies = previous_proxies
            logger.warning(f'{cl.MAGENTA}Буде використано попередній список проксі{cl.RESET}')
        else:
            logger.error(f'{cl.RED}Не знайдено робочих проксі - зупиняємо атаку{cl.RESET}')
            exit()

    return proxies


def load_provided_proxies(proxies_file):
    content = read_or_fetch(proxies_file)
    if content is None:
        logger.warning(f'{cl.RED}Не вдалося зчитати проксі з {proxies_file}{cl.RESET}')
        return None

    proxies = ProxyUtiles.parseAll([prox for prox in content.split()])
    if not proxies:
        logger.warning(f'{cl.RED}У {proxies_file} не знайдено проксі - перевірте формат{cl.RESET}')
    else:
        logger.info(f'{cl.YELLOW}Зчитано {cl.BLUE}{len(proxies)}{cl.YELLOW} проксі{cl.RESET}')
    return proxies


def load_system_proxies():
    raw = fetch(PROXIES_URL)
    try:
        proxies = ProxyUtiles.parseAll(decrypt_proxies(raw))
    except Exception:
        proxies = []
    if proxies:
        logger.info(f'{cl.YELLOW}Отримано персональну вибірку {cl.BLUE}{len(proxies):,}{cl.YELLOW} проксі зі списку {cl.BLUE}10.000+{cl.RESET}')
    else:
        logger.warning(f'{cl.RED}Не вдалося отримати персональну вибірку проксі{cl.RESET}')
    return proxies
