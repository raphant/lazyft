import copy
import pathlib
import time
import uuid
from typing import Optional

import pandas as pd
import sh
from sqlmodel import Session

from lazyft import logger, paths, regex
from lazyft.backtest.commands import BacktestCommand
from lazyft.backtest.report import BacktestReportExporter
from lazyft.database import engine
from lazyft.models import BacktestReport, BacktestRepo, BacktestData
from lazyft.paths import BACKTEST_RESULTS_FILE
from lazyft.reports import get_backtest_repo, BacktestExplorer
from lazyft.runner import Runner
from lazyft.util import ParameterTools

logger_exec = logger.bind(type='backtest')


class BacktestMultiRunner:
    def __init__(self, commands: list[BacktestCommand]) -> None:
        self.runners: list[BacktestRunner] = []
        download_list = []
        for c in commands:
            if (
                c.params.download_data
                and (sort := ' '.join(sorted(c.pairs))) not in download_list
            ):
                download_list.append(sort)
                c.download_data()
            self.runners.append(BacktestRunner(c))
        self.errors = []
        self.session_id = str(uuid.uuid4())

    def execute(self):
        self.errors.clear()
        for r in self.runners:
            try:
                r.execute()
            except Exception as e:
                logger.exception(e)
                logger.info('Continuing onto next execution')
            finally:
                if r.error:
                    self.errors.append((r, r.strategy, r.exception))
                    logger.error('Output:\n{}', '\n'.join(r.output_list[-10:]))

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
            r.report.session_id = self.session_id
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
        self.report_id = str(uuid.uuid4())
        self.command = command
        self.strategy = command.strategy
        self.verbose = verbose or command.verbose
        self.min_win_rate = min_win_rate
        self.report: Optional[BacktestReport] = None
        self.exception = None
        self.start_time = None

    @logger.catch(reraise=True)
    def execute(self, background=False):
        self.reset()
        if self.command.hash in BacktestExplorer.get_hashes():
            self.report = BacktestExplorer.get_using_hash(self.command.hash)
            logger.info('Loaded report with same hash - {}', self.command.hash)
            return
        if self.command.id:
            ParameterTools.set_params_file(self.strategy, self.command.id)
        else:
            ParameterTools.remove_params_file(self.strategy)
        logger.debug('Running command: "{}"', self.command.command_string)
        logger_exec.info('Running command: "{}"', self.command.command_string)
        logger.debug(self.command.params)
        logger.info(
            'Backtesting {} with params id "{}" - {}',
            self.strategy,
            self.command.id or 'null',
            self.command.hash,
        )
        self.start_time = time.time()
        # remove interval from CLI to let strategy handle it
        new_command = copy.copy(self.command)
        new_command.params.interval = ''
        try:
            self.process: sh.RunningCommand = sh.freqtrade(
                new_command.command_string.split(' '),
                _out=lambda log: self.sub_process_log(log, False),
                _err=lambda log: self.sub_process_log(log, False),
                _cwd=str(paths.BASE_DIR),
                _bg=True,
                _done=self.on_finished,
            )
            self.running = True
            self.write_worker.start()
            if not background:
                try:
                    self.process.wait()
                except KeyboardInterrupt:
                    self.process.process.signal_group()
        except sh.ErrorReturnCode as e:
            # logger.error('Sh returned an error ')
            self.exception = e

    def on_finished(self, _, success, _2):
        logger.info('Elapsed time: {:.2f}', time.time() - self.start_time)
        self.running = False
        if not success:
            self.error = True
            logger.error('{} backtest failed with errors', self.strategy)
        else:
            logger.success('{} backtest completed successfully', self.strategy)
            try:
                logger.debug('Generating report...')
                self.report = self.generate_report()
                logger.debug('Report generated')
            except Exception as e:
                logger.exception(e)
                raise

    def generate_report(self):
        json_file = regex.backtest_json.findall(self.output)[0]
        report = BacktestReport(
            _backtest_data=BacktestData(
                text=pathlib.Path(
                    paths.USER_DATA_DIR, 'backtest_results', json_file
                ).read_text()
            ),
            hyperopt_id=self.command.id,
            hash=self.command.hash,
            exchange=self.command.config['exchange']['name'],
            # report_id=self.report_id,
            # hyperopt_id=self.command.id,
            pairlist=self.command.pairs,
            tag=self.command.params.tag,
            ensemble=','.join(
                ['-'.join(s.as_pair) for s in self.command.params.ensemble]
            ),
        )
        return report

    @property
    def log_path(self) -> pathlib.Path:
        return paths.BACKTEST_LOG_PATH.joinpath(self.report_id + '.log')

    def sub_process_log(self, text="", out=False, error=False):
        self.write_queue.put(text)
        logger_exec.info(text.strip())
        super().sub_process_log(text, out, error)

    def save(self):
        with Session(engine) as session:
            report = self.report
            session.add(report)
            session.commit()
            session.refresh(report)
            logger.info('Created report: {}'.format(report))
            if self.log_path.exists():
                self.log_path.rename(
                    paths.BACKTEST_LOG_PATH.joinpath(str(report.id) + '.log')
                )

    def dataframe(self):
        if not self.report:
            raise ValueError('No report to export.')
        performance = {'strategy': self.strategy, **self.report.performance.dict()}
        return pd.DataFrame([performance])
