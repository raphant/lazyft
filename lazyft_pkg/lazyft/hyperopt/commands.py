from lazyft import logger
from lazyft.command import Command
from lazyft.pairlist import Pairlist
from lazyft.parameters import HyperoptParameters
from lazyft.quicktools import QuickTools


class HyperoptCommand(Command):
    def __init__(
        self,
        strategy: str,
        hyperopt_parameters: HyperoptParameters,
        id=None,
        verbose: bool = False,
    ) -> None:
        super().__init__(strategy=strategy, params=hyperopt_parameters, id=id)
        self.verbose = verbose
        self.secret_config = hyperopt_parameters.secrets_config
        self.pairs = hyperopt_parameters.pairs
        if id and not self.pairs:
            # load pairs from ID if pairs not already provided.
            self.pairs = Pairlist.load_from_id(strategy=strategy, id=id)


def create_commands(
    hyperopt_parameters: HyperoptParameters,
    verbose=False,
    skip_data_download=False,
):
    """

    Args:
        hyperopt_parameters:
        pairs:
        verbose:
        skip_data_download:
    Returns:
    """
    """Create `HyperoptCommand` for each strategy in strategies."""
    if hyperopt_parameters.pairs:
        hyperopt_parameters.config = hyperopt_parameters.config.tmp()
        hyperopt_parameters.config.update_whitelist(hyperopt_parameters.pairs)
        hyperopt_parameters.config.save()
    if not skip_data_download:
        QuickTools.download_data(
            config=hyperopt_parameters.config,
            interval=hyperopt_parameters.interval,
            days=hyperopt_parameters.days,
            timerange=hyperopt_parameters.timerange,
            verbose=verbose,
        )
    commands = []
    for s, id in hyperopt_parameters.strategy_id_pairs:
        command = HyperoptCommand(
            s,
            hyperopt_parameters=hyperopt_parameters,
            verbose=verbose,
            id=id,
        )
        commands.append(command)
    return commands
