import os
import random
from concurrent.futures import as_completed
from time import time

import requests
from yarl import URL

from PyRoxy import Proxy
from core import logger, cl, PROXIES_URL
from dns_utils import resolve_host


def download_proxies():
    response = requests.get(PROXIES_URL, timeout=10)
    for line in response.iter_lines(decode_unicode=True):
        yield Proxy.fromString(line)


def update_proxies(thread_pool, period, targets, proxy_timeout):
    #  Avoid parsing proxies too often when restart happens
    if os.path.exists('files/proxies/proxies.txt'):
        last_update = os.path.getmtime('files/proxies/proxies.txt')
        if (time() - last_update) < period / 2:
            logger.info(f'{cl.GREEN}Використовується список проксі з попереднього запуску{cl.RESET}')
            return

    logger.info(f'{cl.GREEN}Завантажуємо список проксі...{cl.RESET}')
    Proxies = list(set(download_proxies()))
    random.shuffle(Proxies)

    size = len(targets)
    logger.info(
        f'{cl.YELLOW}Перевіряємо на працездатність {cl.BLUE}{len(Proxies):,}{cl.YELLOW}'
        f' проксі - це може зайняти пару хвилин:{cl.RESET}'
    )

    future_to_proxy = {}
    for target, chunk in zip(targets, (Proxies[i::size] for i in range(size))):
        resolved_target = URL(target).with_host(resolve_host(target))
        future_to_proxy.update({
            thread_pool.submit(proxy.check, resolved_target, proxy_timeout): proxy
            for proxy in chunk
        })

    CheckedProxies = [
        future_to_proxy[future]
        for future in as_completed(future_to_proxy) if future.result()
    ]

    if not CheckedProxies:
        logger.error(
            'Не знайдено робочих проксі. '
            'Переконайтеся що інтернет з`єднання стабільне і ціль доступна. '
            'Перезапустіть Docker'
        )
        exit()

    logger.info(f'{cl.YELLOW}Знайдено робочих проксі: {cl.BLUE}{len(CheckedProxies):,}{cl.RESET}')

    os.makedirs('files/proxies/', exist_ok=True)
    with open('files/proxies/proxies.txt', 'w') as wr:
        for proxy in CheckedProxies:
            wr.write(str(proxy) + '\n')
