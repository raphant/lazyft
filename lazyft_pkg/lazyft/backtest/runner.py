import pathlib

import pandas as pd
import sh

from lazyft import logger, paths, regex
from lazyft.backtest.commands import BacktestCommand
from lazyft.backtest.report import BacktestReport
from lazyft.reports import Parameter, BacktestReportBrowser
from lazyft.runner import Runner

logger_exec = logger.bind(exec=True)
logger_exec.add(
    pathlib.Path(paths.BASE_DIR, 'backtest.log'),
    retention="5 days",
    rotation='1 MB',
    format='{message}',
)


class BacktestMultiRunner:
    def __init__(self, commands: list[BacktestCommand]) -> None:
        self.runners: list[BacktestRunner] = []
        for c in commands:
            self.runners.append(BacktestRunner(c))

    def execute(self):
        for r in self.runners:
            r.execute()

    def get_totals(self):
        assert any(self.reports), "No reports found."
        frames = [r.totals for r in self.reports]
        return pd.concat(frames)

    def save(self):
        for r in self.reports:
            r.save()

    @property
    def reports(self):
        return [r.report for r in self.runners]

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
        self.report: BacktestReport = None

    def execute(self, background=False):
        self.reset()
        if self.command.hash in BacktestReportBrowser().get_hashes(self.strategy):
            logger.info(
                '{}{}: Loading report with same hash...',
                self.strategy,
                '-' + self.command.id if self.command.id else '',
            )
            self.report = BacktestReport.from_dict(
                self.strategy,
                BacktestReportBrowser().get_backtest_by_hash(
                    self.strategy, self.command.hash
                ),
            )
            return
        if self.command.id:
            Parameter.set_params_file(self.strategy, self.command.id)
        else:
            Parameter.reset_id(self.strategy)
        logger.debug('Running command: "{}"', self.command.command_string)
        logger.debug(self.command.params)
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
            raise RuntimeError('Backtest failed with errors')
        else:
            try:
                logger.debug('Generating report...')
                self.report = self.generate_report()
                logger.debug('Report generated')

            except Exception as e:
                logger.exception(e)
                raise

    def generate_report(self):
        json_file = regex.backtest_json.findall(self.output)[0]
        return BacktestReport(
            self.strategy, json_file, self.command.hash, id=self.command.id
        )

    def sub_process_log(self, text="", out=False, error=False):
        logger_exec.info(text.strip())
        super().sub_process_log(text, out, error)
