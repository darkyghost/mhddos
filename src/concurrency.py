from concurrent.futures import Future, Executor
from concurrent.futures.thread import _WorkItem
import queue
from threading import Lock, Thread

from src.core import logger

_TERMINATE = object()

class DaemonThreadPool(Executor):

    def __init__(self, num_workers: int = 32):
        self._queue = queue.SimpleQueue()
        self._num_workers = num_workers

    def start_all(self):
        for cnt in range(self._num_workers):
            try:
                Thread(target=self._worker, daemon=True).start()
            except RuntimeError:
                logger.warning(f'{cl.RED}Не вдалося запустити атаку - вичерпано ліміт потоків системи{cl.RESET}')
                exit()
        return self

    def submit(self, fn, *args, **kwargs):
        f = Future()
        w = _WorkItem(f, fn, args, kwargs)
        self._queue.put(w)
        return f

    def _worker(self):
        while True:
            work_item = self._queue.get(block=True)
            if work_item is _TERMINATE:
                return

            if work_item is not None:
                work_item.run()
                del work_item


class AtomicCounter:

    def __init__(self, initial=0):
        self.value = initial
        self._lock = Lock()

    def __iadd__(self, value):
        self.increment(value)
        return self

    def __int__(self):
        return self.value

    def increment(self, num=1):
        with self._lock:
            self.value += num

    def reset(self, value=0):
        with self._lock:
            old = self.value
            self.value = value
        return old

