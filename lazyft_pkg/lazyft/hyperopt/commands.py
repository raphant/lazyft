import pathlib

import typer
from lazyft import logger
from lazyft.quicktools import QuickTools
from lazyft.quicktools.config import Config
from lazyft.quicktools.hyperopt import QuickHyperopt

logger = logger.getChild("hyperopt.commands")


class HyperoptCommand:
    def __init__(self, config: Config, strategy: str) -> None:
        self.config = config
        self.strategy = strategy
        self.command_string = ""

    def build_command(
        self,
        interval: str,
        epochs: int,
        min_trades: int,
        spaces: list[str],
        loss_function: str,
        days: int = None,
        timerange=None,
    ):
        assert days or timerange, "--days or --timerange must be specified"
        args_list = []
        args_list.append(f"hyperopt")
        args_list.append(f"-s {self.strategy}")
        timerange = timerange or QuickTools.get_timerange(
            days, interval, self.config, False
        )
        args_list.append(f"--timerange {timerange}")
        args_list.append(f"--spaces {spaces}")
        args_list.append(f"-e {epochs}")
        args_list.append(f"--min-trades {min_trades}")
        args_list.append(f"-i {interval}")

        args_list.append(f"-c {str(self.config.path)}")
        if loss_function != "ShortTradeDurHyperOptLoss":
            args_list.append(f"--hyperopt-loss {loss_function}")
        self.command_string = " ".join(args_list)


def new_hyperopt_cli(
    strategies: list[str] = typer.Argument(...),
    interval: str = typer.Option("5m", "-i", "--interval"),
    epochs: int = typer.Option(100, "-e", "-epochs"),
    config: pathlib.Path = typer.Option("config.json", "-c", "--config"),
    min_trades: int = typer.Option(100, "-m", "--min-trades"),
    spaces: str = typer.Option(
        "sbSr",
        "-s",
        "--spaces",
        help=QuickHyperopt.spaces_help,
    ),
    loss_function: str = typer.Option(
        "0", "-L", "--loss-function", help=QuickHyperopt.losses_help
    ),
    days: int = typer.Option(90, "-d", "--days"),
    timerange: str = typer.Option(None, "-t", "--timerange"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):

    return create_commands(
        strategies,
        config,
        days,
        epochs,
        interval,
        loss_function,
        min_trades,
        spaces,
        timerange,
    )


def create_commands(
    strategies: list[str],
    config="config.json",
    days=90,
    epochs=100,
    interval="5m",
    loss_function="0",
    min_trades=100,
    spaces="sbSr",
    timerange=None,
    skip_backtest=False
):
    """Create `HyperoptCommand` for each strategy in strategies."""
    logger.debug(strategies)
    config = Config(config)
    spaces = QuickHyperopt.get_spaces(spaces)
    loss_function = QuickHyperopt.get_loss_func(loss_function)
    if not skip_backtest:
        QuickTools.download_data(config, interval=interval, days=days, timerange=timerange)
    commands = []
    for s in strategies:
        command = HyperoptCommand(config, s)
        command.build_command(
            interval, epochs, min_trades, spaces, loss_function, days, timerange
        )
        commands.append(command)
    return commands
