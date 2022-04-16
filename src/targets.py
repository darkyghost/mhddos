from .core import logger, cl
from .system import read_or_fetch

from typing import Dict, Optional

from dns import inet
from yarl import URL


Options = Dict[str, str]


class Target:
    url: URL
    method: Optional[str]
    options: Options
    addr: Optional[str]

    def __init__(
        self,
        url: URL,
        method: Optional[str] = None,
        options: Optional[Options] = None,
        addr: Optional[str] = None
    ):
        self.url = url
        self.method = method
        self.options = options or {}
        self.addr = addr

    @classmethod
    def from_string(cls, raw: str) -> "Target":
        parts = [part.strip() for part in raw.split(" ")]
        n_parts = len(parts)
        url = URL(Target.prepare_url(parts[0]))
        method = parts[1].upper() if n_parts > 1 else None
        options = dict(tuple(part.split("=")) for part in parts[2:])
        addr = url.host if inet.is_address(url.host) else None
        return cls(url, method, options, addr)

    @staticmethod
    def prepare_url(target: str) -> str:
        if '://' in target:
            return target

        try:
            _, port = target.split(':', 1)
        except ValueError:
            port = '80'

        scheme = 'https://' if port == '443' else 'http://'
        return scheme + target

    @property
    def is_resolved(self) -> bool:
        return self.addr is not None

    @property
    def is_udp(self) -> bool:
        return self.url.scheme == "udp"

    def option(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.options.get(key, default)

    def __hash__(self):
        return hash(id(self))


class Targets:
    def __init__(self, targets, config):
        self.targets = targets
        self.config = config
        self.config_targets = []

    def __iter__(self):
        self.load_config()
        for target in self.targets + self.config_targets:
            yield Target.from_string(target)

    def load_config(self):
        if not self.config:
            return

        config_content = read_or_fetch(self.config)
        if config_content is None:
            logger.warning(f'{cl.MAGENTA}Не вдалося (пере)завантажити конфіг{cl.RESET}')
            return

        config_targets = []
        for row in config_content.splitlines():
            target = row.strip()
            if target and not target.startswith('#'):
                config_targets.append(target)

        logger.info(f'{cl.YELLOW}Завантажено конфіг {self.config} на {cl.BLUE}{len(config_targets)} цілей{cl.RESET}')
        self.config_targets = config_targets
