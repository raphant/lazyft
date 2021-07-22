import json
import pathlib
import pprint
from typing import Optional, Any, Iterable

import attr
import sh
import typer
from . import study, confirm, logger
from easyft.quicktools.hyperopt import QuickHyperopt
from rich import console
from rich.table import Table


SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.absolute()

print = console.Console().print
spaces_dict = {
    'a': 'all',
    'b': 'buy',
    's': 'sell',
    'S': 'stoploss',
    't': 'trailing',
    'r': 'roi',
}


@attr.s
class Performance:
    trades: int = attr.ib(converter=int)
    wins: int = attr.ib(converter=int)
    losses: int = attr.ib(converter=int)
    draws: int = attr.ib(converter=int)
    avg_profits: float = attr.ib(converter=float)
    med_profit: float = attr.ib(converter=float)
    tot_profit: float = attr.ib(converter=float)
    profit_percent: float = attr.ib(converter=float)
    avg_duration: str = attr.ib()
    loss: float = attr.ib(converter=float)
    seed: int = attr.ib()


class HyperoptRunner:
    pass


class Hyperopt(study.Study):
    strategies = Iterable[SingleCoinStrategy]

    def __init__(
        self,
        coin: str,
        strategies: list[SingleCoinStrategy],
        intervals: Optional[int],
        epochs: Optional[int],
        min_trades: Optional[int],
        spaces: Optional[list],
        days: int,
        loss_function: str,
        **kwargs,
    ) -> None:
        super().__init__(coin, strategies, days, **kwargs)
        self.max_intervals = intervals
        self.epochs = epochs
        self.process = None
        self.running = False
        self.min_trades = min_trades
        self.run_logs: list[str] = []
        self.results: list[study.Result] = []
        self.spaces = spaces
        self.current_interval = 0
        self.final = {}
        self.loss_function = loss_function

    def run(self) -> None:
        self.running = True

        for strategy in self.strategies:
            self._current_strategy = strategy
            try:
                self._run(strategy)
            except sh.ErrorReturnCode_2:
                print(self.logs)
                pprint.pprint(self.results)
            except Exception as e:
                pprint.pprint(self.results)
                self.logger.exception(e)
                print(self.logs)

            self.current_interval = 0
        self.running = False

    def _run(self, strategy: SingleCoinStrategy):
        self.log('Hyperopting strategy %s\n' % strategy)
        while self.current_interval < self.max_intervals:
            self.log(
                'Starting interval #%s of %s'
                % (self.current_interval + 1, self.max_intervals)
            )
            if not strategy.id:
                strategy_path = study.StudyManager.TEMPLATE_DIR
            else:
                strategy_path = strategy.create_strategy(self.coin)
                # self.log(str(strategy_path) + '\n')
            self._start_hyperopt(strategy, strategy_path)
            self.extract_output()
            self.sub_process_logs.clear()
            # self._logs.append(self.EndInterval())
            self.current_interval += 1

    def _start_hyperopt(self, strategy, strategy_path):
        sh.freqtrade(
            'hyperopt',
            [f'-s {s}' for s in self.spaces],
            s=strategy.proper_name,
            userdir=study.StudyManager.FT_DATA_DIR.absolute(),
            c=self.config_path.absolute(),
            e=self.epochs,
            hyperopt_loss=self.loss_function,
            no_color=True,
            print_json=True,
            min_trades=self.min_trades,
            timerange=self.hyperopt_timerange,
            strategy_path=strategy_path,
            _err=lambda log: self.sub_process_log(log, False),
            _out=lambda log: self.sub_process_log(log, True),
        )

    def log(self, text: Any = ''):
        text = str(text)
        ignored_strings = ['{"params":', 'Wins/Draws/Losses.', 'Best result']
        if any([s in text for s in ignored_strings]):
            return super().debug(text)
        super().log(text)

    @staticmethod
    def format(params: dict):
        dictionary = {}

        if 'params' in params:
            bs = params.pop('params')
            buy_params = {}
            sell_params = {}
            for k, v in bs.items():
                d = buy_params if 'buy' in k else sell_params
                try:
                    d[k] = float(v)
                except:
                    d[k] = v
            if buy_params:
                dictionary['buy_params'] = buy_params
            if sell_params:
                dictionary['sell_params'] = sell_params
        dictionary.update(**params)
        return dictionary

    def extract_output(self, *args):
        self.debug('Extracting output...')
        search = regex.FINAL_REGEX.search(self.logs)
        if search:
            formatted = (
                self.sub_process_logs[-1]
                .strip()
                .replace('"True"', 'true')
                .replace('"False"', 'false')
                .replace('"none"', 'null')
            )
            from easyft import SingleCoinStrategy

            seed_search = regex.SEED_REGEX.search(self.logs)
            seed = seed_search.groups()[0]
            result = study.Result(
                self._current_strategy,
                self.format(json.loads(formatted)),
                self.study_path,
                performance=Performance(**search.groupdict(), seed=seed),
                id=self._current_strategy.new_id if self._current_strategy.id else '',
            )
            if result.performance.tot_profit < 0:
                return

            result.save()
            self.log(result.performance)
            self.results.append(result)


def new_hyperopt_cli(
    strategies: list[str] = typer.Argument(...),
    coin: str = typer.Argument(...),
    intervals: int = typer.Option(50, '-I', '--intervals'),
    epochs: int = typer.Option(100, '-e', '-epochs'),
    min_trades: int = typer.Option(100, '-m', '--min-trades'),
    spaces: str = typer.Option(
        'sbSr',
        '-s',
        '--spaces',
        help=QuickHyperopt.spaces_help,
    ),
    loss_function: str = typer.Option(
        '0', '-L', '--loss-function', help=QuickHyperopt.losses_help
    ),
    days: int = typer.Option(90, '-d', '--days'),
    verbose: bool = typer.Option(False, '-v', '--verbose'),
):

    logger.debug(strategies)

    handler = study.StudyManager()
    hyperopt = handler.new_hyperopt(
        coin,
        intervals=intervals,
        epochs=epochs,
        min_trades=min_trades,
        spaces=QuickHyperopt.get_spaces(spaces),
        days=days,
        verbose=verbose,
        strategies=SingleCoinStrategy.create_strategies(strategies, coin),
        loss_function=QuickHyperopt.get_loss_func(loss_function),
    )

    hyperopt.start()
    hyperopt.join()
    logger.info('Post hyperopt')
    results = sorted(
        hyperopt.results, key=lambda r: r.performance.tot_profit, reverse=True
    )
    if not any(results):
        exit(1)
    # print(sorted(results, key=lambda result: result.performance.loss))
    print('\nResults: ', end='')
    # best: study.Result = max(results, key=lambda result: result.performance.tot_profit)

    hyperopt.log(hyperopt.results)

    new_confirm = confirm.Confirm(
        coin, hyperopt.results, days, verbose=verbose, skip_download_data=True
    )
    new_confirm.start()
    new_confirm.join()
    if not any(new_confirm.results):
        exit(1)
    c = console.Console()
    new_confirm.debug(new_confirm.results)
    columns = list(new_confirm.results.values())[-1][-1].keys()
    for k, v in new_confirm.results.items():
        table = Table(*columns, title=f"{k} Results")
        for perf in v:
            table.add_row(*[str(s) for s in perf.values()])
        c.print(table)
    # printable = [f'{k}:{", ".join(v)}' for k, v in new_confirm.results.items()]
    # new_confirm.log(sorted(printable))
