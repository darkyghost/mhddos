import logging
import random
from collections import namedtuple
from pathlib import Path
from threading import Lock
from typing import Tuple

from colorama import Fore


logging.basicConfig(format='[%(asctime)s - %(levelname)s] %(message)s', datefmt="%H:%M:%S")
logger = logging.getLogger('mhddos_proxy')
logger.setLevel('INFO')

ROOT_DIR = Path(__file__).parent.parent

PROXIES_URL = random.choice((
    'https://raw.githubusercontent.com/porthole-ascend-cinnamon/proxy_scraper/main/working_proxies.txt',
    'https://raw.githubusercontent.com/porthole-ascend-cinnamon/proxy_scraper/main/working_proxies2.txt',
    'https://raw.githubusercontent.com/porthole-ascend-cinnamon/proxy_scraper/main/working_proxies3.txt',
))
IT_ARMY_CONFIG_URL = 'https://gist.githubusercontent.com/ddosukraine2022/f739250dba308a7a2215617b17114be9/raw/mhdos_targets_tcp_v2.txt'
VERSION_URL = 'https://raw.githubusercontent.com/porthole-ascend-cinnamon/mhddos_proxy/main/version.txt'

UDP_THREADS = 1
LOW_RPC = 1000

THREADS_PER_CORE = 1000
MAX_DEFAULT_THREADS = 4000

WORK_STEALING_DISABLED = -1

DNS_WORKERS = 10

PADDING_THREADS = 30

class cl:
    MAGENTA = Fore.LIGHTMAGENTA_EX
    BLUE = Fore.LIGHTBLUE_EX
    GREEN = Fore.LIGHTGREEN_EX
    YELLOW = Fore.LIGHTYELLOW_EX
    RED = Fore.LIGHTRED_EX
    RESET = Fore.RESET


Params = namedtuple('Params', 'target, method')


class Stats:
    def __init__(self):
        self._requests: int = 0
        self._bytes: int = 0
        self._lock = Lock()

    def get(self) -> Tuple[int, int]:
        with self._lock:
            return self._requests, self._bytes

    def track(self, rs: int, bs: int) -> None:
        with self._lock:
            self._requests += rs
            self._bytes += bs

    def reset(self) -> Tuple[int, int]:
        with self._lock:
            current = self._requests, self._bytes
            self._requests, self._bytes = 0, 0
        return current
