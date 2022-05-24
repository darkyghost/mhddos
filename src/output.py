import os
from typing import List

from tabulate import tabulate

from .core import CPU_COUNT, CPU_PER_PROCESS, DEFAULT_THREADS, cl, logger
from .i18n import translate as t
from .mhddos import Tools
from .targets import TargetStats


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def show_statistic(
    statistics: List[TargetStats],
    table: bool,
    use_my_ip: int,
    num_threads: int,
    num_proxies: int,
    overtime: bool,
    print_banner_args,
):
    tabulate_text = []
    total_pps, total_bps, total_in_flight = 0, 0, 0
    for stats in statistics:
        (target, method, sig) = stats.target
        method_sig = f" ({sig})" if sig is not None else ""
        pps, bps, in_flight_conn = stats.reset()
        total_pps += pps
        total_bps += bps
        total_in_flight += in_flight_conn
        if table:
            tabulate_text.append((
                f'{cl.YELLOW}%s' % target.url.host,
                target.url.port,
                method,
                Tools.humanformat(in_flight_conn),
                Tools.humanformat(pps) + "/s",
                f'{Tools.humanbits(bps)}/s{cl.RESET}'
            ))
        else:
            logger.info(
                f"{cl.YELLOW}{t('Target')}:{cl.BLUE} {target.human_repr()}, "
                f"{cl.YELLOW}{t('Port')}:{cl.BLUE} {target.url.port}, "
                f"{cl.YELLOW}{t('Method')}:{cl.BLUE} {method}{method_sig}, "
                f"{cl.YELLOW}{t('Connections')}:{cl.BLUE} {Tools.humanformat(in_flight_conn)}, "
                f"{cl.YELLOW}{t('Requests')}:{cl.BLUE} {Tools.humanformat(pps)}/s, "
                f"{cl.YELLOW}{t('Traffic')}:{cl.BLUE} {Tools.humanbits(bps)}/s"
                f"{cl.RESET}"
            )

    if table:
        headers = [
            f"{cl.BLUE}{t('Target')}",
            t('Port'),
            t('Method'),
            t('Connections'),
            t('Requests'),
            f"{t('Traffic')}{cl.RESET}"
        ]

        tabulate_text.append(headers)

        tabulate_text.append((
            f"{cl.GREEN}{t('Total')}",
            '',
            '',
            Tools.humanformat(total_in_flight),
            Tools.humanformat(total_pps) + "/s",
            f'{Tools.humanbits(total_bps)}/s{cl.RESET}'
        ))

        cls()
        print(tabulate(
            tabulate_text,
            headers=headers,
            tablefmt='fancy_grid'
        ))
    else:
        logger.info(
            f"{cl.GREEN}{t('Total')}: "
            f"{cl.YELLOW}{t('Connections')}:{cl.GREEN} {Tools.humanformat(total_in_flight)}, "
            f"{cl.YELLOW}{t('Requests')}:{cl.GREEN} {Tools.humanformat(total_pps)}/s, "
            f"{cl.YELLOW}{t('Traffic')}:{cl.GREEN} {Tools.humanbits(total_bps)}/s{cl.RESET}"
        )

    if print_banner_args:
        print_banner(print_banner_args)

    print_progress(num_threads, num_proxies, use_my_ip, overtime)


def print_progress(
    num_threads: int,
    num_proxies: int,
    use_my_ip: int,
    overtime: bool,
):
    message = f"{cl.YELLOW}{t('Threads')}: {cl.BLUE}{num_threads}{cl.RESET} | "
    if num_proxies:
        message += f"{cl.YELLOW}{t('Proxies')}: {cl.BLUE}{num_proxies}{cl.RESET}"
        if use_my_ip:
            message += f" | {cl.MAGENTA}{t('The attack also uses your IP/VPN')} {cl.RESET}"
        logger.info(message)
    else:
        logger.info(
            message + f"{cl.MAGENTA}{t('Only your IP/VPN is used (no proxies)')}{cl.RESET}"
        )

    if overtime:
        logger.warning(
            f"{cl.MAGENTA}{t('Delay in execution of operations detected')} - "
            f"{t('the attack continues, but we recommend reducing the workload')} `-t`{cl.RESET}"
        )


def print_banner(args):
    rows = []
    if not args.lang:
        rows.append(
            f"- {cl.YELLOW}Change language / Зміна мови:{cl.BLUE} `--lang en` / `--lang ua`{cl.RESET}"
        )
    if not args.threads:
        rows.append(
            f"- {cl.YELLOW}{t('Workload (number of threads)')}:{cl.BLUE} {t('use flag `-t XXXX`, default is')} {DEFAULT_THREADS}"
        )
    elif args.threads > 10000 and args.copies == 1 and CPU_COUNT > CPU_PER_PROCESS:
        rows.append(
            f"- {cl.CYAN}{t('Instead of high `-t` value consider using')} {cl.YELLOW}`--copies 2`{cl.RESET}"
        )
    if not (args.debug or args.table):
        rows.append(
            f"- {cl.YELLOW}{t('Show statistics as a table or text')}:{cl.BLUE} {t('use flag `--table` or `--debug`')}"
        )
    if not args.use_my_ip:
        rows.append(
            f"- {cl.MAGENTA}{t('Consider adding your IP/VPN to the attack - use flag `--vpn`')}{cl.RESET}"
        )
    rows.append(
        f"- {cl.YELLOW}{t('Complete documentation')}:{cl.RESET} - https://github.com/porthole-ascend-cinnamon/mhddos_proxy"
    )

    print()
    print(*rows, sep='\n')
    print()
