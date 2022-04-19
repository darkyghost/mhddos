from concurrent.futures import Executor
from functools import lru_cache
from typing import List, Optional

import dns.exception
import dns.resolver
from yarl import URL

from .core import logger, cl
from .targets import Target


resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = ['1.1.1.1', '1.0.0.1', '8.8.8.8', '8.8.4.4', '208.67.222.222', '208.67.220.220']


@lru_cache(maxsize=1024)
def resolve_host(host: str) -> str:  # TODO: handle multiple IPs?
    if dns.inet.is_address(host):
        return host
    answer = resolver.resolve(host)
    return answer[0].to_text()


def resolve_url(url: str) -> str:
    return resolve_host(URL(url).host)


def safe_resolve_host(host: str) -> Optional[str]:
    try:
        return resolve_host(host)
    except dns.exception.DNSException:
        logger.warning(f'{cl.RED}Ціль {host} не резолвиться і не буде атакована{cl.RESET}')
        return None


def resolve_all_targets(targets: List[Target], thread_pool: Executor) -> List[Target]:
    unresolved_hosts = list(set(target.url.host for target in targets if not target.is_resolved))
    ips = dict(zip(unresolved_hosts, thread_pool.map(safe_resolve_host, unresolved_hosts)))
    for target in targets:
        if not target.is_resolved:
            target.addr = ips.get(target.url.host)
    return targets
