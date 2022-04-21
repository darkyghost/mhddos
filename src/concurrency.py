from concurrent.futures import Future, Executor
from concurrent.futures.thread import _WorkItem
import queue
from threading import Thread

from src.core import logger, cl

TERMINATE = object()

class DaemonThreadPool(Executor):

    def __init__(self, num_workers: int = 32):
        self._queue = queue.SimpleQueue()
        self._num_workers = num_workers

    def start_all(self):
        for _ in range(self._num_workers):
            try:
                Thread(target=self._worker, daemon=True).start()
            except RuntimeError:
                logger.warning(f'{cl.RED}Не вдалося запустити атаку - вичерпано ліміт потоків системи{cl.RESET}')
                exit()
        return self

    def terminate_all(self):
        for _ in range(self._num_workers):
            self._queue.put(TERMINATE)

    def submit(self, fn, *args, **kwargs):
        f = Future()
        w = _WorkItem(f, fn, args, kwargs)
        self._queue.put(w)
        return f

    def _worker(self):
        while True:
            work_item = self._queue.get(block=True)
            if work_item is TERMINATE:
                return

            if work_item is not None:
                work_item.run()
                del work_item
