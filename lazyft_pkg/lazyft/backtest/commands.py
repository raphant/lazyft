import pathlib
from typing import Optional, Union

import typer
from loguru import logger

from lazyft.quicktools import QuickTools
from lazyft.quicktools.config import Config


class BacktestCommand:
    def __init__(self, config: Config, strategy: str, id=None, verbose=False) -> None:
        self.config = config
        self.strategy = strategy
        self.command_string = ''
        self.id = id
        self.verbose = verbose

    def build_command(
        self,
        interval: str,
        days: int = None,
        timerange=None,
    ):
        assert days or timerange, "--days or --timerange must be specified"
        timerange_ = timerange or QuickTools.get_timerange(
            days, interval, self.config, True
        )
        args_list = [
            f'backtesting',
            f'-s {self.strategy}',
            f'--timerange {timerange_}',
            f'-i {interval}',
            f"-c {str(self.config.path)}",
        ]
        self.command_string = ' '.join(args_list)


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
    verbose=False,
    skip_backtest=False,
):
    """Create `HyperoptCommand` for each strategy in strategies."""
    logger.debug(strategies)
    config = Config(config)
    logger.debug('Using config: {}', config.path)
    commands = []
    if not skip_backtest:
        QuickTools.download_data(
            config, interval=interval, days=days, timerange=timerange
        )
    for s in strategies:
        command = BacktestCommand(config, s, id=id, verbose=verbose)
        command.build_command(interval, days, timerange)
        commands.append(command)
    return commands
