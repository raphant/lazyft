import pathlib
from typing import Optional, Union

import typer

from lazyft import logger, util
from lazyft.command import Command
from lazyft.config import Config
from lazyft.pairlist import Pairlist
from lazyft.parameters import GlobalParameters, CommandParameters, command_map
from lazyft.quicktools import QuickTools
from lazyft.strategy import Strategy


class BacktestCommand(Command):
    def __init__(
        self,
        strategy: str,
        params: CommandParameters,
        id=None,
        verbose=False,
    ) -> None:
        super().__init__(strategy, params, id=id)
        self.command_args = dict(**params.__dict__)
        self.backtest_params = params
        self.config = params.config
        self.strategy = strategy
        self.id = id
        self.verbose = verbose
        self.pairs = params.pairs or params.config.whitelist
        self.args = ['backtesting', f'-s {strategy}']
        if id and not self.pairs:
            # load pairs from ID if pairs not already provided.
            self.pairs = Pairlist.load_from_id(strategy=strategy, id=id)
        # self.config = Strategy.init_config(config=config, strategy=strategy)
        self.secret_config = params.secrets_config

    @property
    def hash(self):
        """To help avoid running the same backtest"""
        # sort for consistency
        return util.hash(
            ''.join(sorted(self.command_string))
            + self.id
            + self.config['exchange']['name']
        )


def new_hyperopt_cli(
    strategies: list[str] = typer.Argument(...),
    days: int = typer.Option(None, '-d', '--days'),
    timerange: str = typer.Option('', '-t', '--timerange'),
    interval: str = typer.Option('5m', '-i', '--interval'),
    config: pathlib.Path = typer.Option('config.json', '-c', '--config'),
    verbose: bool = typer.Option(False, '-v', '--verbose'),
):

    return create_commands(
        strategies=strategies,
        interval=interval,
        config=config,
        timerange=timerange,
        verbose=verbose,
        days=days,
    )


def create_commands(
    backtest_params: CommandParameters,
    verbose=False,
    skip_data_download=True,
):
    """Create `HyperoptCommand` for each strategy in strategies."""
    if backtest_params.secrets_config:
        backtest_params.secrets_config = Config(backtest_params.secrets_config)
    logger.debug('Using config: {}', backtest_params.config.path)
    commands = []
    if backtest_params.pairs:
        backtest_params.config = backtest_params.config.tmp()
        backtest_params.config.update_whitelist(backtest_params.pairs)
        backtest_params.config.save()
    if not skip_data_download:
        QuickTools.download_data(
            backtest_params.config,
            interval=backtest_params.intervals_to_download,
            days=backtest_params.days,
            timerange=backtest_params.timerange,
        )
    for s, id in backtest_params.strategy_id_pairs:
        command = BacktestCommand(
            s,
            backtest_params,
            id=id,
            verbose=verbose,
        )
        commands.append(command)
    return commands
