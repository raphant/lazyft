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
        self.output_list = []
        self.verbose = verbose
        self.console = Console(width=127)
        self.process: Optional[RunningCommand] = None
        self.running = False

    @abstractmethod
    def execute(self, *args, **kwargs):
        pass

    def stop(self):
        if not self.running:
            logger.warn("The command is not currently running")
            return False
        self.process.signal_group(signal.SIGINT)
        return True

    def sub_process_log(self, text="", out=False):
        if not text or "ETA" in text:
            return
        text = text.strip()
        self.output_list.append(text)
        if out or self.verbose:
            self.console.print(text, end="\n")

    @abstractmethod
    def generate_report(self):
        pass

    @property
    def output(self):
        return "\n".join(self.output_list)
