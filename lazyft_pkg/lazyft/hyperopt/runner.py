import logging
import pathlib
import time
from queue import Queue
from threading import Thread

import pandas as pd
import sh
from rich.live import Live
from rich.table import Table

from lazyft import constants, hyperopt, runner
from lazyft.regex import EPOCH_LINE_REGEX

logger = hyperopt.logger.getChild('runner')
logger_exec = logger.getChild('exec')
logger_exec.handlers.clear()
fh = logging.FileHandler(pathlib.Path(constants.BASE_DIR, 'hyperopt.log'), mode='a')
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
logger_exec.addHandler(fh)

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
        self.reports: list[hyperopt.HyperoptReport] = []

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
        auto_generate_report=True,
        verbose: bool = False,
    ) -> None:
        super().__init__(verbose)
        self.command = command
        self.strategy = command.strategy
        self.verbose = verbose or command.verbose
        self.current_epoch = 0
        self.auto_generate_report = auto_generate_report

        self._report = None

    @property
    def report(self) -> hyperopt.HyperoptReport:
        return self._report

    def execute(self, background=False):
        self.reset()
        logger.info('Running command: "%s"', self.command.command_string)
        try:
            self.process = sh.freqtrade(
                self.command.command_string.split(" "),
                no_color=True,
                print_json=True,
                disable_param_export=True,
                _out=lambda log: self.sub_process_log(log),
                _err=lambda log: self.sub_process_log(log),
                _cwd=str(constants.BASE_DIR),
                _bg=True,
                _done=self.on_finished,
            )
            self.running = True

            if not background:
                self.live_output()

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
        logger.info("Finished")
        self.running = False

        if constants.STRATEGY_DIR.joinpath(self.strategy.lower() + '.json').exists():
            constants.STRATEGY_DIR.joinpath(self.strategy.lower() + '.json').unlink()
        if not success:
            self.error = True
            logger.error(self.output)
        else:
            if 'epochs saved' in self.output_list[-1]:
                del self.output_list[-1]
            if self.auto_generate_report:
                self._report = self.generate_report()

    def generate_report(self):
        return hyperopt.HyperoptReport(
            self.command.config, self.output, self.output_list[-1], self.strategy
        )

    def get_results(self):
        data = EPOCH_LINE_REGEX.findall(self.output)
        return pd.DataFrame(data, columns=columns)

    def get_results_as_table(self):
        data = EPOCH_LINE_REGEX.findall(self.output)
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
            search = EPOCH_LINE_REGEX.search(line)
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
            expand=True
        )
        return table
