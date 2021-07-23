import sh
from loguru import logger

from lazyft.backtest.commands import BacktestCommand
from lazyft.constants import BASE_DIR
from lazyft.parameters import ParamsToLoad
from lazyft.quicktools.backtest import BacktestOutputExtractor
from lazyft.runner import Runner


class BacktestRunner(Runner):
    def __init__(
        self, command: BacktestCommand, min_win_rate=5, verbose: bool = False
    ) -> None:
        super().__init__(verbose)
        self.command = command
        self.strategy = command.strategy
        self.verbose = verbose or command.verbose
        self.min_win_rate = min_win_rate

    def execute(self, background=False):
        if self.command.id:
            ParamsToLoad.set_id(self.strategy, self.command.id)
        logger.info('Running command: "{}"', self.command.command_string)
        try:
            self.process: sh.RunningCommand = sh.freqtrade(
                self.command.command_string.split(' '),
                _out=lambda log: self.sub_process_log(log, True),
                _err=lambda log: self.sub_process_log(log, False),
                _cwd=str(BASE_DIR),
                _bg=True,
            )
            self.running = True

            if not background:
                self.process.wait()
        except Exception:
            logger.error(self.output)
            raise

    def generate_report(self):
        return BacktestOutputExtractor.create_report(self.output, self.min_win_rate)
