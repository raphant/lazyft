import pathlib
from typing import Optional, Union

import sh
import typer
from lazyft.constants import FT_DATA_DIR
from lazyft.strategy import Strategy
from loguru import logger
from quicktools import QuickTools
from quicktools.config import Config


class BacktestCommand:
    def __init__(self, config: Config, strategy: Strategy) -> None:
        self.config = config
        self.strategy = strategy
        self.command_string = ''

    def build_command(
        self,
        interval: str,
        days: int = None,
        timerange=None,
    ):
        assert days or timerange, "--days or --timerange must be specified"
        args_list = []
        args_list.append(f'backtesting')
        args_list.append(f'-s {self.strategy.proper_name}')
        timerange_ = timerange or QuickTools.get_timerange(
            days, interval, self.config, True
        )
        args_list.append(f'--timerange {timerange_}')
        args_list.append(f'-i {interval}')

        args_list.append(f"-c {str(self.config.path)}")
        args_list.append(f'--strategy-path {self.strategy.create_strategy().parent}')
        self.command_string = ' '.join(args_list)


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
    strategies: list[str],
    interval: str,
    config: Union[pathlib.Path, str],
    days: int = None,
    timerange: Optional[str] = None,
    verbose=False,
):
    """Create `HyperoptCommand` for each strategy in strategies."""
    logger.debug(strategies)
    config = Config(config)
    logger.debug('Using config: {}', config.path)
    strategies = Strategy.create_strategies(*strategies)
    commands = []
    QuickTools.download_data(config, interval=interval, days=days, timerange=timerange)
    for s in strategies:
        command = BacktestCommand(config, s)
        command.build_command(interval, days, timerange)
        commands.append(command)
    return commands
