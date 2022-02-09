import copy
from typing import Union

from lazyft.command_parameters import (
    BacktestParameters,
    HyperoptParameters,
)


class Command:
    def __init__(self, strategy, params: Union[BacktestParameters, HyperoptParameters], id=None):
        self.strategy = strategy
        self.hyperopt_id = id
        self.config = params.config
        self.params = copy.deepcopy(params)
        self.pairs = None
        self.args = []

    @property
    def command_string(self):
        return self.params.command_string + " " + f'-s {self.strategy}'


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
