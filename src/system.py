import os.path
import time
from contextlib import suppress

import requests

from src.core import VERSION_URL


def fix_ulimits():
    try:
        import resource
    except ImportError:
        return

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < hard:
        with suppress(Exception):
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))


def read_or_fetch(path_or_url):
    if os.path.exists(path_or_url):
        with open(path_or_url, 'r') as f:
            return f.read()
    return fetch(path_or_url)


def fetch(url):
    attempts = 4
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=10)
            return response.text
        except requests.RequestException:
            if attempt != attempts - 1:
                time.sleep(attempt + 1)
    return None


def is_latest_version():
    latest = int(read_or_fetch(VERSION_URL).strip())
    current = int(read_or_fetch('version.txt').strip())
    return current >= latest
