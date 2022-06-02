from lazyft.command import Command
from lazyft.command_parameters import BacktestParameters
from lazyft.config import Config


class BacktestCommand(Command):
    def __init__(
        self,
        strategy: str,
        params: BacktestParameters,
        id=None,
        verbose=False,
    ) -> None:
        super().__init__(strategy, params, id=id)
        self.command_args = dict(**params.__dict__)
        self.backtest_params = params
        self.config: Config = params.config
        self.strategy = strategy
        self.id = id
        self.verbose = verbose
        self.pairs = params.pairs or params.config.whitelist
        self.args = ["backtesting", f"-s {strategy}"]
        self.secret_config = params.secrets_config
