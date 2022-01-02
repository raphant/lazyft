import abc
import logging
import pathlib
import signal
import uuid
from abc import ABCMeta, abstractmethod
from queue import Empty, Queue
from threading import Thread
from typing import Optional

from loguru import logger
from rich.console import Console
from sh import RunningCommand

from lazyft import paths

logger = logging.getLogger(__name__)


class Runner(abc.ABC, metaclass=ABCMeta):
    def __init__(self, verbose=False):
        self.report_id = str(uuid.uuid4())
        self.write_worker = Thread(target=self._writer_thread)
        self.verbose = verbose
        self.console = Console(width=200)
        self.process: Optional[RunningCommand] = None
        self.running = False
        self.write_queue = Queue()
        self.error = False
        self.manually_stopped = False
        self.error_list = []
        self.output_list = []

    def reset(self):
        logger.info('Resetting')
        self.running = False
        self.error = False
        self.error_list = []
        self.output_list = []

    @abstractmethod
    def execute(self, *args, **kwargs):
        pass

    def stop(self):
        if not self.running:
            logger.warning("The command is not currently running")
            return False
        self.manually_stopped = True
        self.process.signal_group(signal.SIGINT)
        return True

    def sub_process_log(self, text="", out=False, error=False):
        if not text or "ETA" in text:
            return
        self.output_list.append(text.strip())
        if out or self.verbose:
            self.console.print(text, end="")
        if error:
            self.error_list.append(text.strip())

    @property
    def output(self):
        return "\n".join(self.output_list)

    @property
    def err_output(self):
        return "\n".join(self.error_list)

    def _writer_thread(self):
        """
        This writes all of the Hyperopt output to the log_path. This is started from execute()
        and will stop running when the queue is empty and the hyperopt is no longer running.
        """
        logger.info('Writer thread started')
        while self.running or not self.write_queue.empty():
            try:
                line = self.write_queue.get(block=True, timeout=0.3)
            except Empty:
                continue
            with self.log_path.open('a+') as f:
                f.write(line)

        logger.info('Writer thread stopped')

    @property
    @abstractmethod
    def log_path(self) -> pathlib.Path:
        """Return the path that all hyperopt output will be logged to"""
        ...
