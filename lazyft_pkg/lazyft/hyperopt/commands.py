from lazyft.command import Command
from lazyft.command_parameters import HyperoptParameters
from lazyft.pairlist import load_pairlist_from_id
from lazyft.quicktools import QuickTools


class HyperoptCommand(Command):
    def __init__(
        self,
        strategy: str,
        params: HyperoptParameters,
        id=None,
        verbose: bool = False,
    ) -> None:
        super().__init__(strategy=strategy, params=params, id=id)
        self.verbose = verbose
        self.secret_config = params.secrets_config
        self.pairs = params.pairs
        if id and not self.pairs:
            # load pairs from ID if pairs not already provided.
            self.pairs = load_pairlist_from_id(id=id)
        if params.download_data:
            self.download_data()


def create_commands(
    hyperopt_parameters: HyperoptParameters,
    verbose=False,
):
    """

    Args:
        hyperopt_parameters:
        pairs:
        verbose:
    Returns:
    """
    """Create `HyperoptCommand` for each strategy in strategies."""
    if hyperopt_parameters.pairs:
        hyperopt_parameters.config_path = str(hyperopt_parameters.config.tmp())
        hyperopt_parameters.config.update_whitelist_and_save(hyperopt_parameters.pairs)
    commands = []
    for s, id in hyperopt_parameters.strategy_id_pairs:
        command = HyperoptCommand(
            s,
            params=hyperopt_parameters,
            verbose=verbose,
            id=id,
        )
        commands.append(command)
    return commands
