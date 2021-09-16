import time
from queue import Queue
from threading import Thread

import pandas as pd
import sh
from rich.live import Live
from rich.table import Table

from lazyft import logger, paths, hyperopt, runner, regex
from lazyft.hyperopt import HyperoptReportExporter
from lazyft.models import HyperoptReport
from lazyft.notify import notify
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
    def __init__(self, commands: list[hyperopt.HyperoptCommand]) -> None:
        self.runners: list[HyperoptRunner] = []
        self.commands = commands
        self.reports: list[hyperopt.HyperoptReportExporter] = []

    def create_runners(self):
        for c in self.commands:
            self.runners.append(HyperoptRunner(c))

    def execute(self):
        for r in self.runners:
            r.execute()

    def generate_reports(self):
        for r in self.runners:
            report = r.generate_report()
            report.save()
            self.reports.append(report)

    def get_best_run(self):
        return max(self.reports, key=lambda r: r.performance.tot_profit)


class HyperoptRunner(runner.Runner):
    def __init__(
        self,
        command: hyperopt.HyperoptCommand,
        verbose: bool = False,
        notify: bool = True,
        autosave=False
    ) -> None:
        super().__init__(verbose)
        self.command = command
        self.verbose = verbose or command.verbose
        self.current_epoch = 0
        self.notify = notify

        self._report = None
        self.report_exporter: HyperoptReportExporter = None
        self.start_time = None
        self.autosave = autosave

    @property
    def strategy(self):
        return self.command.strategy

    @property
    def report(self) -> HyperoptReport:
        return self._report

    def execute(self, background=False):
        if self.running:
            raise RuntimeError('Hyperopt is already running')
        self.reset()
        if self.command.id:
            ParameterTools.set_params_file(self.strategy, self.command.id)
        else:
            ParameterTools.remove_params_file(self.strategy)
        logger.debug(self.command.params)
        logger.debug('Running command: "{}"', self.command.command_string)
        logger_exec.info('Running command: "{}"', self.command.command_string)
        logger.info(
            'Hyperopting {} with id "{}"', self.strategy, self.command.id or 'null'
        )
        self.start_time = time.time()
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

            if not background:
                self.process.wait()

        except Exception:
            logger.error(self.output)
            raise

    def live_output(self):
        table = Printer.create_new_table()
        with Live(table, refresh_per_second=4, console=self.console) as live:
            try:
                while self.running:
                    time.sleep(0.4)
                    live.update(self.get_results_as_table())
            except KeyboardInterrupt:
                pass
        if self.error:
            logger.error('\n'.join(self.error_list[-5:]))

    def on_finished(self, _, success, _2):
        self.running = False
        if not success:
            logger.error("Finished with errors")
            self.error = True
            logger.error(self.output)
            if self.notify:
                notify('Hyperopt Failed', 'Hyperopt finished with errors')

        else:
            logger.success("Finished successfully.")
            if self.notify and not self.manually_stopped:
                notify(
                    'Hyperopt Finished',
                    'Hyperopt finished successfully. Elapsed time: %sminutes '
                    % ((time.time() - self.start_time) // 60),
                )
            self.report_exporter = self.generate_report()
            if self.autosave:
                logger.info('Auto-saved: {}', self.save())

    def save(self):
        model = self.report_exporter.save()
        self._report = model
        return model

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

    def generate_report(self):
        secondary_config = dict(
            starting_balance=self.command.params.starting_balance
            or self.command.config['starting_balance'],
            stake_amount=self.command.params.stake_amount
            or self.command.config['stake_amount'],
            max_open_trades=self.command.params.max_open_trades
            or self.command.config['max_open_trades'],
        )

        return hyperopt.HyperoptReportExporter(
            self.command.config,
            self.output,
            self.strategy,
            balance_info=secondary_config,
            tag=self.command.params.tag,
        )

    def get_results(self):
        data = regex.EPOCH_LINE_REGEX.findall(self.output)
        return pd.DataFrame(data, columns=columns)

    def get_results_as_table(self):
        data = regex.EPOCH_LINE_REGEX.findall(self.output)
        table = Printer.create_new_table()
        for d in data:
            table.add_row(*d)

        return table

    def sub_process_log(self, text="", out=False, error=False):
        logger_exec.info(text.strip())
        super().sub_process_log(text, out, error)


class Extractor(Thread):
    def __init__(self, message_queue: Queue, table: Table):
        super().__init__(daemon=True)
        self.queue = message_queue
        self.table = table

    def run(self):
        while True:
            line = self.queue.get()
            if line == "STOP":
                with self.queue.mutex:
                    self.queue.queue.clear()
                break
            search = regex.EPOCH_LINE_REGEX.search(line)
            if not search:
                continue
            line_info = search.groupdict()
            self.table.add_row(*line_info.values())


class Printer:
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
