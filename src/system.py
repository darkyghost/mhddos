from contextlib import suppress
from sys import platform


def fix_ulimits():
    if platform != 'linux':
        # Available on linux only
        return

    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    with suppress(Exception):
        if soft < hard:
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
