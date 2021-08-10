import pathlib
from typing import Optional

import pandas as pd
import sh

from lazyft import logger, paths, regex
from lazyft.backtest.commands import BacktestCommand
from lazyft.backtest.report import BacktestReportExporter
from lazyft.models import BalanceInfo, BacktestReport, BacktestRepo
from lazyft.paths import BACKTEST_RESULTS_FILE
from lazyft.reports import Parameter, BacktestReportBrowser, BacktestRepoExplorer
from lazyft.runner import Runner

logger_exec = logger.bind(exec=True)
logger_exec.add(
    pathlib.Path(paths.LOG_DIR, 'backtest.log'),
    retention="5 days",
    rotation='1 MB',
    format='{message}',
)


class BacktestMultiRunner:
    def __init__(self, commands: list[BacktestCommand]) -> None:
        self.runners: list[BacktestRunner] = []
        for c in commands:
            self.runners.append(BacktestRunner(c))
        self.errors = []

    def execute(self):
        self.errors.clear()
        for r in self.runners:
            try:
                r.execute()
            except Exception as e:
                self.errors.append((r, r.strategy, r.exception or e))

        if any(self.errors):
            logger.info('Completed with {} errors', len(self.errors))

    def get_totals(self):
        assert any(self.reports), "No reports found."
        frames = [
            {'strategy': r.strategy, **r.performance.dict()} for r in self.reports
        ]
        return pd.DataFrame(frames)

    def save(self):
        for r in [r for r in self.runners if r.report]:
            r.save()

    @property
    def reports(self):
        return [r.report for r in self.runners if r.report]

    def get_best_run(self):
        return max([r.performance.total_profit_market for r in self.reports])


class BacktestRunner(Runner):
    def __init__(
        self, command: BacktestCommand, min_win_rate=1, verbose: bool = False
    ) -> None:
        super().__init__(verbose)
        self.command = command
        self.strategy = command.strategy
        self.verbose = verbose or command.verbose
        self.min_win_rate = min_win_rate
        self.report: Optional[BacktestReport] = None
        self.exception = None

    def execute(self, background=False):
        self.reset()
        if self.command.hash in BacktestRepoExplorer().get_hashes():
            logger.info(
                '{}{}: Loading report with same hash...',
                self.strategy,
                '-' + self.command.id if self.command.id else '',
            )
            self.report = BacktestRepoExplorer().get_using_hash(self.command.hash)
            return
        if self.command.id:
            Parameter.set_params_file(self.strategy, self.command.id)
        else:
            Parameter.reset_id(self.strategy)
        logger.debug('Running command: "{}"', self.command.command_string)
        logger.debug(self.command.params)
        logger.info(
            'Backtesting {} with id "{}" - {}',
            self.strategy,
            self.command.id or 'null',
            self.command.hash,
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
        except sh.ErrorReturnCode as e:
            # logger.error('Sh returned an error ')
            self.exception = e

    def on_finished(self, _, success, _2):
        if not success:
            self.error = True
            logger.error('{} backtest failed with errors', self.strategy)
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
        balance_info = BalanceInfo(
            starting_balance=self.command.params.starting_balance
            or self.command.config['starting_balance'],
            stake_amount=self.command.params.stake_amount
            or self.command.config['stake_amount'],
            max_open_trades=self.command.params.max_open_trades
            or self.command.config['max_open_trades'],
        )
        return BacktestReportExporter(
            self.strategy,
            json_file,
            self.command.hash,
            id=self.command.id,
            exchange=self.command.config['exchange']['name'],
            balance_info=balance_info,
            pairlist=self.command.pairs,
            tags=self.command.params.tags,
        ).export

    def sub_process_log(self, text="", out=False, error=False):
        logger_exec.info(text.strip())
        super().sub_process_log(text, out, error)

    def save(self):
        if not self.report:
            raise ValueError('No report to save.')
        if self.report.hash in BacktestRepoExplorer().get_hashes():
            logger.info('Skipping save - hash already exists - {}', self.report.hash)
            return self.report.id
        if not BACKTEST_RESULTS_FILE.exists():
            BACKTEST_RESULTS_FILE.write_text('{}')
        existing_data = BacktestRepo.parse_file(BACKTEST_RESULTS_FILE)
        existing_data.reports.append(self.report)
        BACKTEST_RESULTS_FILE.write_text(existing_data.json())
        return self.report.id

    def dataframe(self):
        if not self.report:
            raise ValueError('No report to export.')
        performance = {'strategy': self.strategy, **self.report.performance.dict()}
        return pd.DataFrame([performance])
