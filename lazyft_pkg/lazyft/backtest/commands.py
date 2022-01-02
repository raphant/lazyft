from lazyft import logger, util
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
        self.args = ['backtesting', f'-s {strategy}']
        # self.config = Strategy.init_config(config=config, strategy=strategy)
        self.secret_config = params.secrets_config
        self._hash = ''

    @property
    def hash(self):
        """To help avoid running the same backtest"""
        # sort for consistency
        if self._hash:
            return self._hash
        command_string = (
            ''.join(sorted(self.command_string.split()))
            + self.id
            + self.config['exchange']['name']
            + self.params.tag
        )
        if self.params.ensemble:
            command_string += ','.join([str(s) for s in self.params.ensemble])
        # logger.debug('Hashing "{}"', command_string)

        self._hash = util.hash(command_string)
        logger.debug('Command hash: ', self._hash)
        return self._hash


# def create_commands(
#     backtest_params: BacktestParameters,
#     verbose=False,
# ):
#     """Create `HyperoptCommand` for each strategy in strategies."""
#     logger.debug('Using config: {}', backtest_params.config.path)
#     commands = []
#     for s, id in backtest_params.strategy_id_pairs:
#         command = BacktestCommand(
#             s,
#             backtest_params,
#             id=id,
#             verbose=verbose,
#         )
#         commands.append(command)
#     return commands
