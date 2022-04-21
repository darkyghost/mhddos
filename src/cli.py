import argparse
import random
from multiprocessing import cpu_count

from .core import THREADS_PER_CORE, MAX_DEFAULT_THREADS, UDP_THREADS, WORK_STEALING_DISABLED
from .mhddos import Methods


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
        help='URL or local path to file with attack targets',
    )
    parser.add_argument(
        '-t',
        '--threads',
        type=int,
        default=min(THREADS_PER_CORE * cpu_count(), MAX_DEFAULT_THREADS),
        help=f'Total number of threads to run (default is CPU * {THREADS_PER_CORE})',
    )
    parser.add_argument(
        '--udp-threads',
        type=int,
        default=UDP_THREADS,
        help=f'Total number of threads to run for UDP sockets (defaults to {UDP_THREADS})',
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
        default=['GET', random.choice(['POST', 'STRESS'])],
        choices=Methods.LAYER7_METHODS,
        help='List of HTTP(s) attack methods to use. Default is GET + POST|STRESS',
    )
    parser.add_argument(
        '--proxies',
        help='URL or local path to file with proxies to use',
    )
    parser.add_argument(
        '--itarmy',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--switch-after',
        type=int,
        default=100,
        help=(
            "Advanced setting. Make sure to test performance when setting non-default value. "
            "Defines how many cycles each threads executes over specific target before "
            "switching to another one. "
            f"Set to {WORK_STEALING_DISABLED} to disable switching (old mode)"
        ),
    )

    parser.add_argument('-p', '--period', type=int, help='DEPRECATED')
    parser.add_argument('--proxy-timeout', type=float, help='DEPRECATED')
    return parser
