from contextlib import suppress
from sys import platform


def fix_ulimits():
    if platform != 'linux':
        return

    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < hard:
        with suppress(Exception):
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
