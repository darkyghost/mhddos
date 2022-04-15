from .core import logger, cl
from .system import read_or_fetch

from dataclasses import dataclass, field
from typing import Dict, Optional

from yarl import URL


@dataclass
class Target:
    url: URL
    method: Optional[str] = None
    params: Dict[str, str] = field(default_factory=dict)
    addr: Optional[str] = None

    @classmethod
    def from_string(cls, raw: str) -> "Target":
        parts = [part.strip() for part in raw.split(" ")]
        n_parts = len(parts)
        url = Target.prepare_url(parts[0])
        method = parts[1].upper() if n_parts > 1 else None
        params = dict(tuple(part.split("=")) for part in parts[2:])
        return cls(URL(url), method, params)

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
