from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import dns.exception
import dns.resolver
from yarl import URL

from .core import logger, cl


resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = ['1.1.1.1', '1.0.0.1', '8.8.8.8', '8.8.4.4', '208.67.222.222', '208.67.220.220']


@lru_cache(maxsize=128)
def resolve_host(url):  # TODO: handle multiple IPs?
    host = URL(url).host
    if dns.inet.is_address(host):
        return host
    answer = resolver.resolve(host)
    return answer[0].to_text()


def get_resolvable_targets(targets, thread_pool):
    targets = list(set(targets))
    if not targets:
        return targets

    future_to_target = {
        thread_pool.submit(resolve_host, target): target
        for target in targets
    }
    for future in as_completed(future_to_target):
        target = future_to_target[future]
        try:
            future.result()
            yield target
        except dns.exception.DNSException:
            logger.warning(f'{cl.RED}Ціль {target} не резолвиться і не буде атакована{cl.RESET}')
