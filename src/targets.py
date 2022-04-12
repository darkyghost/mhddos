from .core import logger, cl
from .system import read_or_fetch


class Targets:
    def __init__(self, targets, config):
        self.targets = targets
        self.config = config
        self.config_targets = []

    def __iter__(self):
        self.load_config()
        for target in self.targets + self.config_targets:
            yield self.prepare_target(target)

    def prepare_target(self, target):
        if '://' in target:
            return target

        try:
            _, port = target.split(':', 1)
        except ValueError:
            port = '80'

        scheme = 'https://' if port == '443' else 'http://'
        return scheme + target

    def load_config(self):
        if not self.config:
            return

        config_content = read_or_fetch(self.config)
        if config_content is None:
            logger.warning(f'{cl.MAGENTA}Не вдалося (пере)завантажити конфіг{cl.RESET}')
            return

        self.config_targets = [
            target.strip()
            for target in config_content.split()
            if target.strip()
        ]

        logger.info(f'{cl.YELLOW}Завантажено конфіг {self.config} на {cl.BLUE}{len(self.config_targets)} цілей{cl.RESET}')
