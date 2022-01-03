from __future__ import annotations

import pathlib
import time
from collections import Counter
from queue import Queue
from threading import Thread
from typing import Optional

import freqtrade
import freqtrade.commands as ft_commands
import freqtrade.optimize.hyperopt
import pandas as pd
import rapidjson
from freqtrade.optimize import hyperopt_tools
from rich.live import Live
from rich.table import Table
from sqlmodel import Session

from lazyft import logger, paths, hyperopt, runner, regex, util
from lazyft.database import engine
from lazyft.models import HyperoptReport
from lazyft.notify import notify_pb
from lazyft.util import ParameterTools

logger_exec = logger.bind(type='hyperopt')
columns = [
    "Epoch",
    "Trades",
    "Win Draw Loss",
    "Avg profit",
    "Profit",
    "Avg duration",
    "Max Drawdown",
    "Objective",
]


class HyperoptManager:
    def __init__(self, commands: list[hyperopt.HyperoptCommand], autosave: bool = True) -> None:
        """
        Runs multiple instances of HyperoptRunner sequentially.

        :param commands: A list of HyperoptCommand objects that will be passed to the runner.
        :param autosave: If True, the results will be saved to the database on completion.
        """
        self.commands = commands
        self.autosave = autosave
        self.stop_flag = False
        self.running = False

        self.queue = Queue()
        self.reports: list[hyperopt.HyperoptReportExporter] = []
        self.runners: list[HyperoptRunner] = []
        self.current_runner: Optional[HyperoptRunner] = None
        self.failed_runners: list[HyperoptRunner] = []
        self.thread: Optional[Thread] = None
        for c in self.commands:
            self.queue.put(HyperoptRunner(c, autosave=True))
            self.runners.append(HyperoptRunner(c))

    def execute(self):
        """
        Executes the hyperopt commands in a non-blocking way.

        :return: The thread object.
        """
        logger.info('Hyperopting in the background')
        thread = Thread(target=self._runner)
        thread.start()
        self.thread = thread
        return thread

    def _runner(self):
        """
        Runs each HyperoptRunner found in the queue.
        """
        self.running = True
        while not self.queue.empty() and not self.stop_flag:
            r: HyperoptRunner = self.queue.get(timeout=5)
            self.current_runner = r
            # noinspection PyBroadException
            try:
                r.execute()

            finally:
                self.on_finished(r)
        self.running = False
        self.current_runner = None
        notify_pb('Hyperopt Manager', 'Finished hyperopting')

    def on_finished(self, runner: 'HyperoptRunner'):
        """
        Called when a runner finishes.

        :param runner: The runner that finished.
        :return: None
        """
        if runner.error:
            logger.error('Failed while hyperopting {}', runner.strategy)
            logger.error(runner.output[-300:])
            self.failed_runners.append(runner)
        else:
            logger.info('Hyperopt finished {}', runner.strategy)
            if self.autosave:
                runner.save()

    def stop(self):
        """
        Stops the hyperopt manager and clears the queue.

        :return: None
        """
        # clear queue
        while not self.queue.empty():
            self.queue.get(block=False)
        self.current_runner.stop()

    # def generate_reports(self):
    #     for r in self.runners:
    #         sh.freqtrade('hyperopt-show --best'.split())
    #         report = r.generate_report()
    #         report.save()
    #         self.reports.append(report)


# noinspection PyTypeChecker
class HyperoptRunner(runner.Runner):
    lock = False

    def __init__(
        self,
        command: hyperopt.HyperoptCommand,
        autosave=False,
        notify: bool = True,
        verbose: bool = False,
    ) -> None:
        """
        Runs a single instance of HyperoptRunner.

        :param command: A HyperoptCommand object.
        :param autosave: If True, the results will be saved to the database on completion.
        :param notify: If True, a notification will be sent on finish.
        :param verbose: If True, more output will be printed to the console.
        """
        super().__init__(verbose)
        self.command = command
        self.verbose = verbose or command.verbose
        self.notify = notify
        self.autosave = autosave
        self._report = None
        self.start_time = None
        self.exception: Optional[Exception] = None
        self.counter = Counter()
        self.log(str(self.command.command_string))
        if self.command.hyperopt_id:
            self.log(f'Hyperopt ID: {self.command.hyperopt_id}')
        # self.command.params.logfile = self.log_path

    @property
    def strategy(self):
        return self.command.strategy

    @property
    def report(self) -> HyperoptReport:
        return self._report

    def pre_execute(self):
        """
        Initializes the HyperoptRunner.
        """
        if HyperoptRunner.lock:
            raise RuntimeError('Hyperopt is already running')
        self.reset()
        # set or remove parameter file in strategy directory
        if self.command.hyperopt_id:
            ParameterTools.set_params_file(self.command.hyperopt_id)
        else:
            ParameterTools.remove_params_file(self.strategy, self.command.config.path)
        logger.debug(self.command.params)
        logger.debug('Running command: "{}"', self.command.command_string)
        logger_exec.info('Running command: "{}"', self.command.command_string)
        logger.info(
            'Hyperopting {} with id "{}"',
            self.strategy,
            self.command.hyperopt_id or 'null',
        )
        HyperoptRunner.lock = True

    def execute(self, background=False):
        """
        Executes the Hyperopt command.

        :param background: If True, the command will be executed in the background.
        """
        # validate run
        self.pre_execute()
        split = self.command.command_string.split()
        pargs = ft_commands.Arguments(split).get_parsed_arg()
        self.running = True
        self.start_time = time.time()
        if background:
            pargs['print_colorized'] = False
            freqtrade.optimize.hyperopt.print = self.log
            hyperopt_tools.print = self.log
            self.write_worker.start()
        # Execute VIA sh
        try:
            ft_commands.start_hyperopt(pargs)
        # except OperationalException as e:
        # if str(e) == 'No data found. Terminating.':
        #     if self.counter['no_data'] > 1:
        #         raise e
        #     self.counter['no_data'] += 1
        #     downloader.download_missing_historical_data(
        #         self.strategy, self.command.config, self.command.params
        #     )
        #     return self.execute(background)
        # self.exception = e
        except Exception as e:
            self.exception = e
            success = False
        else:
            success = True

        self.on_finished(success)

    def join(self):
        while self.running or not self.write_queue.empty():
            time.sleep(1)

    @property
    def output(self):
        return self.log_path.read_text()

    def live_output(self):
        """Use rich lib to display an updatable table with epoch information"""
        table = _Printer.create_new_table()
        with Live(table, refresh_per_second=4, console=self.console) as live:
            try:
                while self.running:
                    time.sleep(0.4)
                    live.update(self._get_results_as_table())
            except KeyboardInterrupt:
                pass
        if self.error:
            logger.error('\n'.join(self.error_list[-5:]))

    def _get_results_as_table(self):
        """Generates tables for live_output"""
        data = regex.EPOCH_LINE_REGEX.findall(self.output)
        table = _Printer.create_new_table()
        for d in data:
            table.add_row(*d)

        return table

    def on_finished(self, success: bool):
        """The callback for the sh command in execute()"""
        HyperoptRunner.lock = False
        ParameterTools.remove_params_file(self.strategy, self.command.config.path)
        try:
            if not success:
                logger.error("Finished with errors")
                self.error = True
                logger.error(self.output)
                if self.notify:
                    notify_pb('Hyperopt Failed', 'Hyperopt finished with errors')

            else:
                logger.success("Finished successfully.")
                if self.notify and not self.manually_stopped:
                    notify_pb(
                        'Hyperopt Finished',
                        'Hyperopt finished successfully. Elapsed time: %sminutes '
                        % ((time.time() - self.start_time) // 60),
                    )
                try:
                    self._report = self.generate_report()
                except IndexError:
                    return
                self.log(str(self._report))
                logger.debug('Report generated')
                if self.autosave:
                    logger.info('Auto-saved: {}', self.save())
        finally:
            self.running = False
        freqtrade.optimize.hyperopt.print = print
        hyperopt_tools.print = print
        self.write_worker.join()

    def save(self, epoch=None) -> HyperoptReport:
        """
        Save the the hyperopt result to the database.

        :param epoch: An optional epoch to save. If None, the best epoch is used.
        :return: The saved report
        """
        if not self._report:
            raise ValueError('No report available')
        with Session(engine) as session:
            report = self.report
            if epoch:
                report = self.report.new_report_from_epoch(epoch)
            session.add(report)
            session.commit()
            session.refresh(report)
            logger.info('Created report id: {}'.format(report.id))
            self.log_path.rename(paths.HYPEROPT_LOG_PATH.joinpath(str(report.id) + '.log'))
            self.report_id = report.id

        self._report = report
        return report

    def log(self, *args):
        """For logging purposes. Fills the write_queue"""
        text = ''.join(args)
        print(*args)
        logger_exec.info(text)
        self.write_queue.put(text + '\n')
        # if out or self.verbose:
        #     self.console.print(text, end="")
        # if error:
        #     self.error_list.append(text)

    def get_epoch_report(self, epoch: int) -> HyperoptReport:
        """
        Get the report for a specific epoch.

        :param epoch: The epoch to get the report for.
        :return: The report for the epoch.
        """
        hyperopt_file = pathlib.Path(
            paths.LAST_HYPEROPT_RESULTS_FILE.parent,
            rapidjson.loads(paths.LAST_HYPEROPT_RESULTS_FILE.read_text())['latest_hyperopt'],
        ).resolve()
        # noinspection PyUnresolvedReferences
        report = HyperoptReport(
            hyperopt_file_str=str(hyperopt_file),
            epoch=epoch - 1,
            exchange=self.command.config['exchange'],
        )
        return report

    def generate_report(self):
        """Creates a report that can saved later on."""
        hyperopt_file = pathlib.Path(
            paths.LAST_HYPEROPT_RESULTS_FILE.parent,
            rapidjson.loads(paths.LAST_HYPEROPT_RESULTS_FILE.read_text())['latest_hyperopt'],
        ).resolve()
        # noinspection PyUnresolvedReferences
        self._report = HyperoptReport(
            exchange=self.command.config.exchange,
            epoch=util.get_best_hyperopt(),
            hyperopt_file_str=str(hyperopt_file),
            tag=self.command.params.tag,
        )
        return self._report

    def get_results(self) -> pd.DataFrame:
        """Scrapes the hyperopt epoch information using regex and returns a DataFrame"""
        data = regex.EPOCH_LINE_REGEX.findall(self.log_path.read_text())
        return pd.DataFrame(data, columns=columns)

    @property
    def log_path(self) -> pathlib.Path:
        """
        Returns the path to the log file.
        """
        return paths.HYPEROPT_LOG_PATH.joinpath(self.report_id + '.log')


class _Printer:
    @staticmethod
    def create_new_table():
        table = Table(
            *columns,
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
            expand=True,
        )
        return table
