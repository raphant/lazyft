from typing import TYPE_CHECKING

import typer
from easyft import confirm, util, study

if TYPE_CHECKING:
    from easyft import SingleCoinStrategy, Strategy


class SingleCoinBacktest(confirm.Confirm):
    def __init__(
        self, strategy: 'SingleCoinStrategy', coin: str, id_: str, days: int, **kwargs
    ) -> None:
        super().__init__(coin, [], days, **kwargs)
        self.study_results = [study.Result.from_params(strategy, id_, self.study_path)]
        # self.log('Downloading %s days worth of market data for %s\n' % (days, coin))
        # sh.freqtrade(
        #     'download-data',
        #     days=days,
        #     c=self.config_path,
        #     userdir=constants.FT_DATA_DIR,
        # )
        self.log('Creating strategy with id %s' % id_)
        strategy.create_strategy_with_param_id(self.coin, id_)
        self.log('Testing range is %s\n' % util.escape_ansi(self.backtest_timerange))


def new_backtest(
    strategy: str = typer.Argument(...),
    coin: str = typer.Argument(...),
    param_id: str = typer.Argument(...),
    days: int = typer.Argument(...),
    verbose: bool = typer.Option(False, '-v', '--verbose'),
):
    from easyft import SingleCoinStrategy

    strategy = SingleCoinStrategy(strategy)
    backtest = SingleCoinBacktest(strategy, coin, param_id, days=days, verbose=verbose)
    backtest.start()
    backtest.join()
    backtest.log(backtest.results)


class Backtest(SingleCoinBacktest):
    def __init__(self, strategy: 'Strategy', id_: str, days: int, **kwargs) -> None:
        super().__init__(strategy, None, id_, days, **kwargs)
        self.study_results = [study.Result.from_params(strategy, id_, self.study_path)]
        # self.log('Downloading %s days worth of market data for %s\n' % (days, coin))
        # sh.freqtrade(
        #     'download-data',
        #     days=days,
        #     c=self.config_path,
        #     userdir=constants.FT_DATA_DIR,
        # )
        self.log('Creating strategy with id %s' % id_)
        strategy.create_strategy_with_param_id(self.coin, id_)
        self.log('Testing range is %s\n' % util.escape_ansi(self.backtest_timerange))
