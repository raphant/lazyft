import pathlib

import pandas as pd
import sh
from loguru import logger

from lazyft import paths
from lazyft.backtest.commands import BacktestCommand
from lazyft.backtest.report import BacktestReport
from lazyft.parameters import Parameter
from lazyft.runner import Runner

logger_exec = logger.bind(name='backtest')
logger_exec.remove()
logger_exec.add(
    pathlib.Path(paths.BASE_DIR, 'backtest.log'), mode='a', format='{message}'
)


class BacktestMultiRunner:
    def __init__(self, commands: list[BacktestCommand]) -> None:
        self.runners: list[BacktestRunner] = []
        for c in commands:
            self.runners.append(BacktestRunner(c))
        self.reports: list[BacktestReport] = []

    def execute(self):
        for r in self.runners:
            r.execute()

    def generate_reports(self):
        for r in self.runners:
            report = r.generate_report()
            self.reports.append(report)

    def get_totals(self):
        assert any(self.reports), "No reports found."
        frames = [r.totals for r in self.reports]
        return pd.concat(frames)

    def save(self):
        for r in self.reports:
            if not r.id:
                continue
            r.save()

    def get_best_run(self):
        return max([r.total_profit for r in self.reports])


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
            Parameter.set_params_file(self.strategy, self.command.id)
        else:
            Parameter.reset_id(self.strategy)
        logger.debug('Running command: "{}"', self.command.command_string)
        logger.info(
            'Backtesting {} with id "{}"', self.strategy, self.command.id or 'null'
        )
        try:
            self.process: sh.RunningCommand = sh.freqtrade(
                self.command.command_string.split(' '),
                _out=lambda log: self.sub_process_log(log, False),
                _err=lambda log: self.sub_process_log(log, False),
                _cwd=str(paths.BASE_DIR),
                _bg=True,
                _done=self.on_finished,
            )
            self.running = True
            if not background:
                try:
                    self.process.wait()
                except KeyboardInterrupt:
                    self.process.process.signal_group()
        except Exception:
            logger.error(self.output)
            raise

    def on_finished(self, _, success, _2):
        if not success:
            self.error = True

    def generate_report(self):
        return BacktestReport.from_output(
            self.strategy,
            self.output,
            self.min_win_rate,
            id=self.command.id,
        )

    def sub_process_log(self, text="", out=False, error=False):
        logger_exec.info(text.strip())
        super().sub_process_log(text, out, error)
