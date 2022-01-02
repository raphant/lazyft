from typing import Union

from lazyft import downloader
from lazyft.command_parameters import (
    command_map,
    BacktestParameters,
    HyperoptParameters,
)


class Command:
    def __init__(self, strategy, params: Union[BacktestParameters, HyperoptParameters], id=None):
        self.strategy = strategy
        self.hyperopt_id = id
        self.config = params.config
        self.params = params
        self.pairs = None
        self.args = []
        if params.download_data:
            downloader.download_missing_historical_data(strategy, self.config, params)

    @property
    def command_string(self):
        params = self.params
        args = self.args.copy()

        for key, value in params.__dict__.items():
            if not value or key not in command_map or key == 'days':
                continue
            if value is True:
                value = ''
            if key == 'pairs':
                value = ' '.join(value)
            arg_line = f"{command_map[key]} {value}".strip()
            args.append(arg_line)
        return ' '.join(args)


def create_commands(
    parameters: Union[HyperoptParameters, BacktestParameters],
    verbose=False,
):
    """
    Create `HyperoptCommand` for each strategy in strategies.
    Args:
        parameters:
        verbose:
    Returns:
    """
    from lazyft.backtest.commands import BacktestCommand
    from lazyft.hyperopt.commands import HyperoptCommand

    commands = []
    CommandClass = (
        HyperoptCommand if isinstance(parameters, HyperoptParameters) else BacktestCommand
    )
    for s, id in parameters.strategy_id_pairs:
        command = CommandClass(
            s,
            params=parameters,
            verbose=verbose,
            id=id,
        )
        commands.append(command)
    return commands
