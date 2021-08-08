import pathlib
from typing import Optional, Union

import typer
from loguru import logger

from lazyft.config import Config
from lazyft.pairlist import Pairlist
from lazyft.quicktools import QuickTools
from lazyft.strategy import Strategy


class BacktestCommand:
    def __init__(
        self,
        command_args,
        config: Config,
        strategy: str,
        secret_config: Config = None,
        pairs=None,
        id=None,
        verbose=False,
    ) -> None:
        self.command_args = command_args
        self.config = config
        self.strategy = strategy
        self.id = id
        self.verbose = verbose
        self.pairs = pairs or config.whitelist
        if id and not self.pairs:
            # load pairs from ID if pairs not already provided.
            self.pairs = Pairlist.load_from_id(strategy=strategy, id=id)
        self.config = Strategy.init_config(config=config, strategy=strategy)
        self.secret_config = secret_config

    @property
    def command_string(self):
        return self.build_command()

    def build_command(self):
        logger.debug('Building command')
        args = self.command_args
        assert (
            args["days"] or args["timerange"]
        ), "'days' or 'timerange' must be specified"
        timerange = args["timerange"]
        if not timerange:
            _, timerange = QuickTools.get_timerange(
                self.config, args["days"], args["interval"]
            )
        args_list = [
            f'backtesting',
            f'-s {self.strategy}',
            f'--timerange {timerange}',
            f'-i {args["interval"]}',
            f"-c {self.config}",
        ]
        if self.secret_config:
            args_list.append(f"-c {self.secret_config}")
        if self.pairs:
            args_list.append(f'-p {" ".join(self.pairs)}')
        if args["starting_balance"]:
            args_list.append(f'--starting-balance {args["starting_balance"]}')
        if args["max_open_trades"]:
            args_list.append(f'--max-open-trades {args["max_open_trades"]}')
        if args["stake_amount"]:
            args_list.append(f'--stake-amount {args["stake_amount"]}')
        return ' '.join(args_list)


def new_hyperopt_cli(
    strategies: list[str] = typer.Argument(...),
    id: str = typer.Option(None),
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
    strategies: list[str],
    interval: str,
    config: Union[pathlib.Path, str],
    secret_config: Union[pathlib.Path, str] = None,
    days: int = None,
    timerange: Optional[str] = None,
    pairs: list[str] = None,
    starting_balance=None,
    max_open_trades=None,
    stake_amount=None,
    verbose=False,
    skip_data_download=False,
):
    """Create `HyperoptCommand` for each strategy in strategies."""
    logger.debug(strategies)
    strategy_id_pair = []
    for s in strategies:
        if '-' in s:
            strategy_id_pair.append((tuple(s.split('-'))))
        else:
            strategy_id_pair.append((s, ''))
    config = Config(config)
    if secret_config:
        secret_config = Config(secret_config)
    logger.debug('Using config: {}', config.path)
    commands = []
    if not skip_data_download:
        QuickTools.download_data(
            config, interval=interval, days=days, timerange=timerange
        )
    for s, id in strategy_id_pair:
        command_args = dict(
            interval=interval,
            days=days,
            timerange=timerange,
            starting_balance=starting_balance,
            max_open_trades=max_open_trades,
            stake_amount=stake_amount,
        )
        command = BacktestCommand(
            command_args,
            config=config,
            secret_config=secret_config,
            strategy=s,
            id=id,
            pairs=pairs,
            verbose=verbose,
        )
        commands.append(command)
    return commands
