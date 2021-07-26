import abc
from abc import ABCMeta, abstractmethod
from rich.console import Console
from sh import RunningCommand
from typing import Optional
import logging
import signal

logger = logging.getLogger(__name__)


class Runner(abc.ABC, metaclass=ABCMeta):
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.console = Console(width=120)
        self.process: Optional[RunningCommand] = None
        self.running = False
        self.error = False
        self.error_list = []
        self.output_list = []

    def reset(self):
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
        self.process.signal_group(signal.SIGINT)
        return True

    def sub_process_log(self, text="", out=False, error=False):
        if not text or "ETA" in text:
            return
        text = text.strip()
        self.output_list.append(text)
        if out or self.verbose:
            self.console.print(text, end="")
        if error:
            self.error_list.append(text)

    @abstractmethod
    def generate_report(self):
        pass

    @property
    def output(self):
        return "\n".join(self.output_list)

    @property
    def err_output(self):
        return "\n".join(self.error_list)
