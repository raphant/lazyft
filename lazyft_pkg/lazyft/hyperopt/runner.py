import time
from queue import Queue
from threading import Thread

import sh
from lazyft import console, constants, hyperopt, logger, runner
from lazyft.quicktools.regex import EPOCH_LINE_REGEX
from rich.live import Live
from rich.table import Table
import pandas as pd

logger = logger.getChild("hyperopt.runner")
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
            report.params.save()
            self.reports.append(report)

    def get_best_run(self):
        return max(self.reports, key=lambda r: r.performance.tot_profit)


class HyperoptRunner(runner.Runner):
    def __init__(
        self, command: hyperopt.HyperoptCommand, verbose: bool = False
    ) -> None:
        super().__init__(verbose)
        self.command = command
        self.strategy = command.strategy
        self.verbose = verbose

    def execute(self, background=False):
        self.output_list.clear()
        logger.info('Running command: "%s"', self.command.command_string)
        try:
            self.process = sh.freqtrade(
                self.command.command_string.split(" "),
                no_color=True,
                print_json=True,
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
        with Live(table, refresh_per_second=4, console=console) as live:
            try:
                while self.running:
                    time.sleep(0.4)
                    live.update(self.get_results_as_table())
            except KeyboardInterrupt:
                pass

    def sub_process_log(self, text="", out=False):
        if not text or "ETA" in text:
            return
        text = text.strip()
        self.output_list.append(text)

    def on_finished(self, _, success, _2):
        logger.info("Finished")
        self.running = False

        if constants.STRATEGY_DIR.joinpath(self.strategy.lower() + '.json').exists():
            constants.STRATEGY_DIR.joinpath(self.strategy.lower() + '.json').unlink()
        if not success:
            logger.error(self.output)

    def generate_report(self):
        return hyperopt.HyperoptReport(self.output, self.output_list[-1], self.strategy)

    def get_results(self):
        data = EPOCH_LINE_REGEX.findall(self.output)
        return pd.DataFrame(data, columns=columns)

    def get_results_as_table(self):
        data = EPOCH_LINE_REGEX.findall(self.output)
        table = Printer.create_new_table()
        for d in data:
            table.add_row(*d)

        return table


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
            *columns, show_header=True, header_style="bold magenta", show_lines=True
        )
        return table
