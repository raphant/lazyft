import pathlib
import time
from queue import Queue
from threading import Thread
from typing import Optional

import pandas as pd
import rapidjson
import sh
from rich.live import Live
from rich.table import Table
from sqlmodel import Session

from lazyft import logger, paths, hyperopt, runner, regex
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
    def __init__(
        self, commands: list[hyperopt.HyperoptCommand], autosave: bool = True
    ) -> None:
        self.commands = commands
        self.autosave = autosave
        self.stop_flag = False
        self.running = False

        self.queue = Queue()
        self.reports: list[hyperopt.HyperoptReportExporter] = []
        self.runners: list[HyperoptRunner] = []
        self.current_runner: Optional[HyperoptRunner] = None
        self.failed_runners: list[HyperoptRunner] = []
        self.thread: Thread = None
        for c in self.commands:
            self.queue.put(HyperoptRunner(c, autosave=True))
            self.runners.append(HyperoptRunner(c))

    def execute(self):
        logger.info('Hyperopting in the background')
        thread = Thread(target=self._runner)
        thread.start()
        self.thread = thread
        return thread

    def _runner(self):
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
        if runner.error:
            logger.error('Failed while hyperopting {}', runner.strategy)
            logger.error(runner.output[-300:])
            self.failed_runners.append(runner)
        else:
            logger.info('Hyperopt finished {}', runner.strategy)
            if self.autosave:
                runner.save()

    def stop(self):
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


class HyperoptRunner(runner.Runner):
    def __init__(
        self,
        command: hyperopt.HyperoptCommand,
        task_id=None,
        celery=False,
        loaded_from_celery=False,
        autosave=False,
        notify: bool = True,
        verbose: bool = False,
    ) -> None:
        """
        Args:
            command: The command to execute
            task_id: A custom ID to give to the runner. Used as a celery task ID and saving.
            celery: Is this ran by celery?
            loaded_from_celery: Is this loaded with CeleryRunner.load?
            autosave: Should the report be saved after the command completes?
            notify: Should a notification be sent after the command completes?
            verbose: Should debug-level logs be printed?
        """
        super().__init__(verbose, task_id=task_id)
        self.command = command
        self.verbose = verbose or command.verbose
        self.notify = notify
        self.autosave = autosave
        self.loaded_from_celery = loaded_from_celery
        self.celery = celery
        self._report = None
        self.start_time = None
        self.epoch_text = ''

    @property
    def strategy(self):
        return self.command.strategy

    @property
    def report(self) -> HyperoptReport:
        return self._report

    def pre_execute(self):
        if self.loaded_from_celery:
            raise RuntimeError(
                'This hyperopt was loaded from celery and can not be executed.'
            )
        if self.running:
            raise RuntimeError('Hyperopt is already running')
        self.reset()
        # set or remove parameter file in strategy directory
        if self.command.hyperopt_id:
            ParameterTools.set_params_file(self.command.hyperopt_id)
        else:
            ParameterTools.remove_params_file(self.strategy)
        logger.debug(self.command.params)
        logger.debug('Running command: "{}"', self.command.command_string)
        logger_exec.info('Running command: "{}"', self.command.command_string)
        logger.info(
            'Hyperopting {} with id "{}"',
            self.strategy,
            self.command.hyperopt_id or 'null',
        )
        self.start_time = time.time()

    def execute(self, background=False):
        # validate run
        self.pre_execute()

        # Execute VIA sh
        try:
            self.process = sh.freqtrade(
                self.command.command_string.split(" "),
                no_color=True,
                _out=lambda log: self.sub_process_log(log),
                _err=lambda log: self.sub_process_log(log),
                _cwd=str(paths.BASE_DIR),
                _bg=True,
                _done=self.on_finished,
            )
            self.running = True
            logger.info('Process ID: {}', self.process.pid)
            self.write_worker.start()
            if not background:
                try:
                    self.process.wait()
                except KeyboardInterrupt:
                    self.stop()
        except Exception:
            logger.error(self.output)
            raise

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

    def on_finished(self, _, success, _2):
        """The callback for the sh command in execute()"""
        self.running = False
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
            self.write_worker.join()
            self._report = self.generate_report()
            logger.debug('Report generated')
            if self.autosave:
                logger.info('Auto-saved: {}', self.save())

    def save(self):
        """Saves the report to lazy_params.json"""
        if self.loaded_from_celery:
            raise RuntimeError(
                'This hyperopt was loaded from celery and can not be executed.'
            )

        with Session(engine) as session:
            report = self.report
            session.add(report)
            session.commit()
            session.refresh(report)
            logger.info('Created report id: {}'.format(report.id))
            try:
                self.log_path.rename(
                    paths.HYPEROPT_LOG_PATH.joinpath(str(report.id) + '.log')
                )
            except FileNotFoundError:
                pass

        self._report = report
        return report

    # @staticmethod
    # def get_report_backtest(idx=0):
    #     hyperopt_file = pathlib.Path(
    #         paths.LAST_HYPEROPT_RESULTS_FILE.parent,
    #         rapidjson.loads(paths.LAST_HYPEROPT_RESULTS_FILE.read_text())[
    #             'latest_hyperopt'
    #         ],
    #     ).resolve()
    #     results = HyperoptTools.load_previous_results(hyperopt_file)
    #     result = results[idx]
    #
    #     return pd.DataFrame(result['results_metrics']['results_per_pair'])
    @property
    def current_epoch(self):
        findall = regex.CURRENT_EPOCH.findall(self.epoch_text)
        if not findall:
            return 0
        return findall[0]

    def generate_report(self):
        """Creates a report that can saved later on."""
        hyperopt_file = pathlib.Path(
            paths.LAST_HYPEROPT_RESULTS_FILE.parent,
            rapidjson.loads(paths.LAST_HYPEROPT_RESULTS_FILE.read_text())[
                'latest_hyperopt'
            ],
        ).resolve()
        epoch = regex.FINAL_REGEX.findall(self.output)[0][0]
        # noinspection PyUnresolvedReferences
        self._report = HyperoptReport(
            exchange=self.command.config.exchange,
            epoch=int(epoch) - 1,  # -1 because the epoch is incremented for readability
            hyperopt_file_str=str(hyperopt_file),
            tag=self.command.params.tag,
        )
        return self._report

    def get_results(self) -> pd.DataFrame:
        """Scrapes the hyperopt epoch information using regex and returns a DataFrame"""
        data = regex.EPOCH_LINE_REGEX.findall(self.output)
        return pd.DataFrame(data, columns=columns)

    def sub_process_log(self, text="", out=False, error=False):
        """For logging purposes. Fills the write_queue"""
        if not text or "ETA" in text:
            self.epoch_text = text
            return
        logger_exec.info(text.strip())
        self.write_queue.put(text)
        if out or self.verbose:
            self.console.print(text, end="")
        if error:
            self.error_list.append(text.strip())

    @property
    def log_path(self) -> pathlib.Path:
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
