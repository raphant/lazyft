from __future__ import annotations

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
from lazyft.database import engine
from lazyft.models import BacktestReport, BacktestData
from lazyft.reports import get_backtest_repo
from lazyft.runner import Runner
from lazyft.util import ParameterTools

logger_exec = logger.bind(type='backtest')


class BacktestMultiRunner:
    def __init__(self, commands: list[BacktestCommand]) -> None:
        """
        Runs a queue of BacktestRunners. A runner will be created for each command.

        :param commands: list of BacktestCommand objects
        """
        self.runners: list[BacktestRunner] = []
        for c in commands:
            self.runners.append(BacktestRunner(c))
        self.errors = []
        self.session_id = str(uuid.uuid4())
        self.current_runner: Optional[BacktestRunner] = None

    def execute(self):
        """
        Executes all runners in the queue.
        """
        self.errors.clear()
        for r in self.runners:
            self.current_runner = r
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

    def get_totals(self) -> pd.DataFrame:
        """
        Returns a DataFrame with all of the performances.
        """
        assert any(self.reports), "No reports found."
        frames = [{'strategy': r.strategy, **r.performance.dict()} for r in self.reports]
        return pd.DataFrame(frames)

    def save(self):
        """
        Saves all reports to the database.
        """
        for r in [r for r in self.runners if r.report]:
            r.report.session_id = self.session_id
            r.save()

    @property
    def reports(self) -> list[BacktestReport]:
        """
        Returns a list of all reports.
        """
        return [r.report for r in self.runners if r.report]

    def get_best_run(self) -> BacktestReport:
        """
        Returns the best run using the score metric.
        """
        return max(self.reports, key=lambda r: r.performance.score)


class BacktestRunner(Runner):
    def __init__(
        self, command: BacktestCommand, verbose: bool = False, load_from_hash=True
    ) -> None:
        """
        Executes a backtest using the passed commands.

        :param command: A BacktestCommand with the arguments to pass to freqtrade
        :param verbose: If True, will print extra output of the command
        :param load_from_hash: If True, will load the report from the database if it exists
        """
        super().__init__(verbose)
        self.report_id = str(uuid.uuid4())
        self.load_from_hash = load_from_hash
        self.command = command
        self.strategy = command.strategy
        self.verbose = verbose or command.verbose
        self.report: Optional[BacktestReport] = None
        self.exception = None
        self.start_time = None

    @logger.catch(reraise=True)
    def execute(self, background=False):
        """
        Executes the backtest using the passed command.

        :param background: If True, will run in background
        """
        if self.hash_exists():
            self.load_hashed()
            return
        self.pre_execute()
        # remove interval from CLI to let strategy handle it
        new_command = copy.copy(self.command)
        new_command.params.interval = ''
        try:
            self.process: sh.RunningCommand = sh.freqtrade(
                new_command.command_string.split(' '),
                _out=lambda log: self.sub_process_log(log, False),
                _err=lambda log: self.sub_process_log(log, False),
                _cwd=str(paths.BASE_DIR),
                _bg=background,
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

    def pre_execute(self):
        """
        Pre-execution tasks
        """
        self.reset()
        if self.command.id:
            ParameterTools.set_params_file(self.command.id)
        else:
            ParameterTools.remove_params_file(self.strategy, self.command.config.path)
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

    def hash_exists(self):
        if self.load_from_hash and self.command.hash in get_backtest_repo().get_hashes():
            return True
        return False

    # noinspection PyIncorrectDocstring
    def on_finished(self, _, success, _2):
        """
        Callback when the process is finished.

        :param success:  True if the process finished successfully
        """
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
        """
        Generates the report from the output of the backtest.

        :return: BacktestReport
        """
        json_file = regex.backtest_json.findall(self.output)[0]
        report = BacktestReport(
            _backtest_data=BacktestData(
                text=pathlib.Path(paths.USER_DATA_DIR, 'backtest_results', json_file).read_text()
            ),
            hyperopt_id=self.command.id,
            hash=self.command.hash,
            exchange=self.command.config['exchange']['name'],
            # report_id=self.report_id,
            # hyperopt_id=self.command.id,
            pairlist=self.command.pairs,
            tag=self.command.params.tag,
            ensemble=','.join(['-'.join(s.as_pair) for s in self.command.params.ensemble]),
        )
        return report

    @property
    def log_path(self) -> pathlib.Path:
        return paths.BACKTEST_LOG_PATH.joinpath(self.report_id + '.log')

    def sub_process_log(self, text="", out=False, error=False):
        """
        Callback for the subprocess to log the output.

        :param text: text to log
        :param out: True if text is stdout
        :param error: True if text is stderr
        :return: None
        """
        self.write_queue.put(text)
        logger_exec.info(text.strip())
        super().sub_process_log(text, out, error)

    def save(self):
        """
        Saves the report to the database.
        """
        if self.hash_exists():
            logger.info('Skipping save... backtest already exists in the database')
            return self.report
        if not self.report:
            logger.info('Skipping save... no report generated')
            return
        with Session(engine) as session:
            report = self.report
            session.add(report)
            session.add(report._backtest_data)
            session.commit()
            session.refresh(report)
            session.refresh(report._backtest_data)
            logger.info('Created report id {}: {}'.format(report.id, report.performance.dict()))
            if self.log_path.exists():
                self.log_path.rename(paths.BACKTEST_LOG_PATH.joinpath(str(report.id) + '.log'))
        return report

    def dataframe(self):
        if not self.report:
            raise ValueError('No report to export.')
        performance = {'strategy': self.strategy, **self.report.performance.dict()}
        return pd.DataFrame([performance])

    def load_hashed(self):
        self.report = get_backtest_repo().get_using_hash(self.command.hash)
        logger.info('Loaded report with same hash - {}', self.command.hash)
