from __future__ import annotations

import pathlib
import time
import uuid
from typing import Optional

import pandas as pd
from freqtrade.commands import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.enums import RunMode
from freqtrade.exceptions import OperationalException
from freqtrade.optimize import backtesting, optimize_reports
from lazyft import downloader, logger, parameter_tools, paths, strategy, util
from lazyft.backtest.commands import BacktestCommand
from lazyft.database import engine
from lazyft.models import BacktestData, BacktestReport
from lazyft.reports import get_backtest_repo, get_hyperopt_repo
from lazyft.runner import Runner
from lazyft.space_handler import SpaceHandler
from lazyft.util import get_latest_backtest_filename, store_backtest_stats
from sqlmodel import Session

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
        super().__init__(command, verbose)
        self.load_from_hash = load_from_hash
        self.verbose = verbose or command.verbose
        self._hash = None
        # self.report_id = self.command.hash
        # self.command.params.logfile = self.log_path

        self.report: Optional[BacktestReport] = None
        self.exception: Optional[Exception] = None
        self.start_time: Optional[float] = None
        self.result_path: Optional[pathlib.Path] = None

    @property
    def hash(self):
        """To help avoid running the same backtest"""
        if self._hash:
            return self._hash
        try:
            command_string = (
                ''.join(sorted(self.command.command_string.split()))
                + str(self.hyperopt_id)
                + self.config['exchange']['name']
                + self.params.tag
                + (self.strategy_hash or '')
            )
            if self.hyperopt_id:
                command_string += util.hash(
                    get_hyperopt_repo().get(self.hyperopt_id).parameters['params']
                )
        except TypeError as e:
            raise TypeError(
                f'Could not hash command: {self.command.command_string}' f'\n{self.command.params}'
            ) from e
        if self.params.ensemble:
            command_string += ','.join([str(s) for s in self.params.ensemble])
        # logger.debug('Hashing "{}"', command_string)

        self._hash = util.hash(command_string)
        logger.debug('Command hash: {}', self._hash)
        return self._hash

    def pre_execute(self):
        """
        Pre-execution tasks
        """
        self.reset()
        if self.command.id:
            assert (
                get_hyperopt_repo().get(self.command.id).strategy == self.strategy
            ), f'Hyperopt id {self.command.id} does not match strategy {self.strategy}'
            parameter_tools.set_params_file(self.command.id)
        else:
            parameter_tools.remove_params_file(self.strategy, self.config.path)
        # start_backtesting(pargs)
        # Initialize backtesting object

        # freqtrade.optimize.backtesting.print = self.log

        # save copy of strategy
        if not self.hyperopt_id:
            strategy.save_strategy_text_to_database(self.strategy)
        else:
            # check to see if the report with hyperopt id has a strategy hash
            report = get_hyperopt_repo().get(self.hyperopt_id)
            self.export_backup_strategy(report)

        # backtesting.logger = test_logger
        optimize_reports.print = self.log
        if self.params.custom_settings:
            self.update_spaces()
        if self.params.download_data:
            downloader.download_data_for_strategy(self.strategy, self.config, self.params)
        pargs = Arguments(self.command.command_string.split()).get_parsed_arg()
        config = setup_optimize_configuration(pargs, RunMode.BACKTEST)
        bt = backtesting.Backtesting(config)
        config['export'] = None

        logger.info('Running command: "freqtrade {}"', self.command.command_string)
        logger_exec.info('Running command: "freqtrade {}"', self.command.command_string)
        logger.debug(self.params)
        logger.info(
            'Backtesting {} with params id "{}" - {}',
            self.strategy,
            self.command.id or 'null',
            self.hash,
        )
        return bt

    @logger.catch(reraise=True)
    def execute(self):
        if self.hash_exists():
            self.load_hashed()
            return
        success = False
        backtest = self.pre_execute()
        self.start_time = time.time()
        self.running = True
        try:
            backtest.start()
        except OperationalException as e:
            if str(e) == 'No data found. Terminating.':
                raise OperationalException(
                    f'{e}:\nStrategy path: {self.params.strategy_path}\nData path: {self.params.data_dir}'
                ) from e
        except Exception as e:
            # logger.exception(f'Backtest failed: {e}')
            self.exception = e
            success = False
        else:
            self.result_path = store_backtest_stats(
                backtest.config['exportfilename'], backtest.results
            )
            success = True
        self.write_worker.start()
        self.on_finished(success)

    # def execute(self, background=False):
    #     """
    #     Executes the backtest using the passed command.
    #
    #     :param background: If True, will run in background
    #     """
    #     if self.hash_exists():
    #         self.load_hashed()
    #         return
    #     self.pre_execute()
    #     # remove interval from CLI to let strategy handle it
    #     new_command = copy.copy(self.command)
    #     new_command.params.interval = ''
    #     try:
    #         self.process: sh.RunningCommand = sh.freqtrade(
    #             new_command.command_string.split(' '),
    #             _out=lambda log: self.sub_process_log(log, False),
    #             _err=lambda log: self.sub_process_log(log, False),
    #             _cwd=str(paths.BASE_DIR),
    #             _bg=background,
    #             _done=self.on_finished,
    #         )
    #         self.running = True
    #         self.write_worker.start()
    #         if not background:
    #             try:
    #                 self.process.wait()
    #             except KeyboardInterrupt:
    #                 self.process.process.signal_group()
    #     except sh.ErrorReturnCode as e:
    #         # logger.error('Sh returned an error ')
    #         self.exception = e

    def on_finished(self, success):
        try:
            self.running = False
            logger.info('Elapsed time: {:.2f}', time.time() - self.start_time)
            parameter_tools.remove_params_file(self.strategy, self.command.config.path)
            if success:
                self.report = self.generate_report()
                logger.success(f'Backtest {self.strategy} finished successfully')
            else:
                logger.error('{} backtest failed with errors', self.strategy)
                raise self.exception
        finally:
            strategy.delete_temporary_strategy_backup_dir(self.tmp_strategy_path)
            self.write_queue.join()

    def hash_exists(self):
        if self.load_from_hash and self.hash in get_backtest_repo().get_hashes():
            return True
        return False

    # noinspection PyIncorrectDocstring

    # def on_finished(self, _, success, _2):
    #     """
    #     Callback when the process is finished.
    #
    #     :param success:  True if the process finished successfully
    #     """
    #     logger.info('Elapsed time: {:.2f}', time.time() - self.start_time)
    #     self.running = False
    #     if not success:
    #         self.error = True
    #         logger.error('{} backtest failed with errors', self.strategy)
    #     else:
    #         logger.success('{} backtest completed successfully', self.strategy)
    #         try:
    #             logger.debug('Generating report...')
    #             self.report = self.generate_report()
    #             logger.debug('Report generated')
    #         except Exception as e:
    #             logger.exception(e)
    #             raise

    def generate_report(self):
        """
        Generates the report from the output of the backtest.

        :return: BacktestReport
        """
        return BacktestReport(
            # _backtest_data=BacktestData(text=self.result_path.read_text()),
            backtest_file_str=get_latest_backtest_filename(),
            hyperopt_id=self.command.id,
            hash=self.hash,
            exchange=self.command.config['exchange']['name'],
            pairlist=self.command.pairs,
            tag=self.command.params.tag,
            strategy_hash=self.strategy_hash,
            ensemble=','.join(['-'.join(s.as_pair) for s in self.command.params.ensemble]),
        )

    def log(self, *args):
        """For logging purposes. Fills the write_queue"""
        text = ''.join(args)
        print(*args)
        logger_exec.info(text)
        self.write_queue.put(text + '\n')

    @property
    def log_path(self) -> pathlib.Path:
        return (paths.BACKTEST_LOG_PATH / str(self.report_id)).with_suffix('.log')

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

    def print_report(self):
        print(self.report.report_text)

    # noinspection PyProtectedMember
    def save(self, tag: str = None):
        """
        Saves the report to the database.
        """
        if self.hash_exists():
            logger.info('Skipping save... backtest already exists in the database')
            print(self.report.report_text)
            return self.report
        if not self.report:
            logger.info('Skipping save... no report generated')
            return
        if tag:
            self.report.tag = tag
        with Session(engine) as session:
            report = self.report
            session.add(report)
            # session.add(report._backtest_data)
            session.commit()
            session.refresh(report)
            # session.refresh(report._backtest_data)
            logger.info('Created report id {}: {}'.format(report.id, report.performance.dict()))
            if self.log_path.exists():
                self.log_path.rename(paths.BACKTEST_LOG_PATH.joinpath(str(report.id) + '.log'))
                self.report_id = report.id
        return report

    def performance_df(self):
        """
        The function takes the report of the strategy and returns a dataframe with the performance of
        the strategy
        :return: A dataframe with the performance of the strategy.
        """
        if not self.report:
            raise ValueError('No report to export.')
        performance = {'strategy': self.strategy, **self.report.performance.dict()}
        return pd.DataFrame([performance])

    def load_hashed(self):
        """
        It uses the hash to load the report from the database.
        """
        self.report = get_backtest_repo().get_using_hash(self.hash)
        logger.info('Loaded report with same hash - {}', self.hash)

    def update_spaces(self):
        logger.info('Updating custom spaces...')
        sh = SpaceHandler(self.params.strategy_path / strategy.get_file_name(self.strategy))
        sh.reset()
        if self.params.custom_spaces == 'all':
            logger.debug('Enabling all custom spaces')
            sh.set_all_enabled()
        for space in self.params.custom_spaces.split():
            logger.debug(f'Enabling space: {space}')
            sh.add_space(space)
        for s, v in self.params.custom_settings.items():
            logger.debug(f'Setting space-setting: {s} to {v}')
            sh.add_setting(s, v)
        sh.save()
