import os

from tabulate import tabulate

from .core import cl, logger, THREADS_PER_CORE
from .mhddos import Tools


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')



def show_statistic(statistics, refresh_rate, table, vpn_mode, proxies_cnt, period, passed):
    tabulate_text = []
    total_pps = 0
    total_bps = 0
    for params, counters in statistics.items():
        pps = int(counters['requests'].reset() / refresh_rate)
        total_pps += pps
        bps = int(8 * counters['bytes'].reset() / refresh_rate)
        total_bps += bps
        if table:
            tabulate_text.append((
                f'{cl.YELLOW}%s' % params.target.url.host, params.target.url.port, params.method,
                Tools.humanformat(pps), f'{Tools.humanbits(bps)}{cl.RESET}'
            ))
        else:
            logger.info(
                f'{cl.YELLOW}Ціль:{cl.BLUE} %s,{cl.YELLOW} Порт:{cl.BLUE} %s,{cl.YELLOW} Метод:{cl.BLUE} %s'
                f' {cl.YELLOW} PPS:{cl.BLUE} %s,{cl.YELLOW} BPS:{cl.BLUE} %s{cl.RESET}' %
                (
                    params.target.url.host,
                    params.target.url.port,
                    params.method,
                    Tools.humanformat(pps),
                    Tools.humanbits(bps),
                )
            )

    if table:
        tabulate_text.append((f'{cl.GREEN}Усього', '', '', Tools.humanformat(total_pps),
                              f'{Tools.humanbits(total_bps)}{cl.RESET}'))

        cls()
        print(tabulate(
            tabulate_text,
            headers=[f'{cl.BLUE}Ціль', 'Порт', 'Метод', 'Запити/c', f'Трафік/c{cl.RESET}'],
            tablefmt='fancy_grid'
        ))
        print_banner(vpn_mode)

    print_progress(period, passed, proxies_cnt)


def print_progress(period, passed, proxies_cnt):
    logger.info(f'{cl.YELLOW}Новий цикл через: {cl.BLUE}{round(period - passed)} секунд{cl.RESET}')
    if proxies_cnt:
        logger.info(f'{cl.YELLOW}Кількість проксі: {cl.BLUE}{proxies_cnt}{cl.RESET}')
    else:
        logger.info(f'{cl.YELLOW}Атака без проксі - переконайтеся що ви анонімні{cl.RESET}')


def print_banner(vpn_mode):
    print(f'''
- {cl.YELLOW}Навантаження (кількість потоків){cl.RESET} - параметр `-t 3000`, за замовчуванням - CPU * {THREADS_PER_CORE}
- {cl.YELLOW}Статистика у вигляді таблиці або тексту{cl.RESET} - прапорець `--table` або `--debug`
- {cl.YELLOW}Повна документація{cl.RESET} - https://github.com/porthole-ascend-cinnamon/mhddos_proxy
    ''')

    if not vpn_mode:
        print(
            f'        {cl.MAGENTA}Щоб використовувати VPN або власний IP замість проксі - додайте прапорець `--vpn`{cl.RESET}\n')
