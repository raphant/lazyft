from lazyft.command import Command
from lazyft.command_parameters import HyperoptParameters
from lazyft.pairlist import load_pairlist_from_id


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
        self.args = ['hyperopt', f'-s {strategy}']
        if id and not self.pairs:
            # load pairs from ID if pairs not already provided.
            self.pairs = load_pairlist_from_id(id=id)


