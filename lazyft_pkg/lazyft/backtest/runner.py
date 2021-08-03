import logging
import pathlib

import sh

from lazyft import constants
from lazyft.backtest import logger
from lazyft.backtest.commands import BacktestCommand
from lazyft.backtest.report import BacktestReport
from lazyft.constants import BASE_DIR
from lazyft.parameters import ParamsToLoad
from lazyft.runner import Runner

logger = logger.getChild('runner')
logger_exec = logger.getChild('exec')
logger_exec.handlers.clear()
fh = logging.FileHandler(pathlib.Path(constants.BASE_DIR, 'backtest.log'), mode='a')
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
logger_exec.addHandler(fh)


class BacktestRunner(Runner):
    def __init__(
        self, command: BacktestCommand, min_win_rate=1, verbose: bool = False
    ) -> None:
        super().__init__(verbose)
        self.command = command
        self.strategy = command.strategy
        self.verbose = verbose or command.verbose
        self.min_win_rate = min_win_rate

    def execute(self, background=False):
        self.reset()
        if self.command.id:
            ParamsToLoad.set_id(self.strategy, self.command.id)
        logger.info('Running command: "%s"', self.command.command_string)
        try:
            self.process: sh.RunningCommand = sh.freqtrade(
                self.command.command_string.split(' '),
                _out=lambda log: self.sub_process_log(log, False),
                _err=lambda log: self.sub_process_log(log, False),
                _cwd=str(BASE_DIR),
                _bg=True,
                _done=self.on_finished,
            )
            self.running = True

            if not background:
                self.process.wait()
        except Exception:
            logger.error(self.output)
            raise

    def on_finished(self, _, success, _2):
        if not success:
            self.error = True

    def generate_report(self):
        return BacktestReport.from_output(self.strategy, self.output, self.min_win_rate)

    def sub_process_log(self, text="", out=False, error=False):
        logger_exec.info(text.strip())
        super().sub_process_log(text, out, error)
