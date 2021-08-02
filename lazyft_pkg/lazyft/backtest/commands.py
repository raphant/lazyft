import pathlib
from typing import Optional, Union

import typer
from loguru import logger

from lazyft.quicktools import QuickTools
from lazyft.config import Config
from lazyft.strategy import Strategy


class BacktestCommand:
    def __init__(
        self, command_args, config: Config, strategy: str, id=None, verbose=False
    ) -> None:
        self.command_args = command_args
        self.config = config
        self.strategy = strategy
        self.id = id
        self.verbose = verbose
        self.config = Strategy.init_config(config=config, strategy=strategy)

    @property
    def command_string(self):
        return self.build_command()

    def build_command(self):
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
            f"-c {str(self.config.path)}",
        ]
        if args["pairs"]:
            args_list.append(f'-p {" ".join(args["pairs"])}')
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
        id=id,
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
    days: int = None,
    id=None,
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
    config = Config(config)
    logger.debug('Using config: {}', config.path)
    commands = []
    if not skip_data_download:
        QuickTools.download_data(
            config, interval=interval, days=days, timerange=timerange
        )
    for s in strategies:
        command_args = dict(
            interval=interval,
            days=days,
            timerange=timerange,
            pairs=pairs,
            starting_balance=starting_balance,
            max_open_trades=max_open_trades,
            stake_amount=stake_amount,
        )
        command = BacktestCommand(command_args, config, s, id=id, verbose=verbose)
        commands.append(command)
    return commands
