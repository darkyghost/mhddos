import time
from contextlib import suppress
from pathlib import Path

import requests


def fix_ulimits():
    try:
        import resource
    except ImportError:
        return

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < hard:
        with suppress(Exception):
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))


def read_or_fetch(name):
    path = Path(name)
    is_local = path.is_file()
    if is_local:
        return path.read_text()

    attempts = 4
    for attempt in range(attempts):
        try:
            response = requests.get(name, timeout=10)
            return response.text
        except requests.RequestException:
            if attempt != attempts - 1:
                time.sleep(attempt + 1)
    return None
