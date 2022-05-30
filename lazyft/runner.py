from __future__ import annotations

import abc
import logging
import pathlib
import signal
import uuid
from abc import ABCMeta, abstractmethod
from queue import Empty, Queue
from threading import Thread
from typing import Optional, Union, TYPE_CHECKING

from loguru import logger
from rich.console import Console
from sh import RunningCommand

from lazyft import strategy
from lazyft.models import HyperoptReport, StrategyBackup
from lazyft.strategy import get_strategy_hash_and_text

if TYPE_CHECKING:
    from lazyft.backtest.commands import BacktestCommand
    from lazyft.hyperopt import HyperoptCommand

logger = logging.getLogger(__name__)


class Runner(abc.ABC, metaclass=ABCMeta):
    def __init__(self, command: 'Union[BacktestCommand, HyperoptCommand]', verbose=False):
        self.command = command
        self.verbose = verbose

        self.report_id = str(uuid.uuid4())
        self.write_worker = Thread(target=self._writer_thread)
        self.console = Console(width=200)
        self.write_queue = Queue()

        self.process: Optional[RunningCommand] = None

        self.running = False
        self.error = False
        self.manually_stopped = False

        self.error_list = []
        self.output_list = []

        self.strategy_hash = get_strategy_hash_and_text(self.strategy)[0]
        self.tmp_strategy_path = None

    # region Properties
    @property
    @abstractmethod
    def log_path(self) -> pathlib.Path:
        """Return the path that all hyperopt output will be logged to"""
        ...

    @property
    def hyperopt_id(self):
        return self.command.hyperopt_id

    @property
    def params(self):
        return self.command.params

    @property
    def strategy(self):
        return self.command.strategy

    @property
    def config(self):
        return self.command.config

    @property
    def output(self):
        return "\n".join(self.output_list)

    @property
    def err_output(self):
        return "\n".join(self.error_list)

    # endregion

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
                self.write_queue.task_done()

        logger.info('Writer thread stopped')

    def on_finish(self):
        strategy.delete_temporary_strategy_backup_dir(self.tmp_strategy_path)

    def export_backup_strategy(self, report: HyperoptReport) -> None:
        """
        Export the strategy to the backup directory

        :param report: The hyperopt report to export parameters from
        """
        if not report.strategy_hash:
            logger.warning(f'No strategy hash found for report {report.id}...skipping export')
            return
        self.strategy_hash = report.strategy_hash
        sb = StrategyBackup.load_hash(report.strategy_hash)
        new_folder = strategy.create_temp_folder_for_strategy_and_params_from_backup(
            sb, self.hyperopt_id
        )
        self.params.strategy_path = new_folder
        self.params.user_data_dir = new_folder
        self.tmp_strategy_path = new_folder
        logger.info(f'Using strategy hash {sb.hash} in backup: {new_folder}')
