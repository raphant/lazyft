import pathlib
from typing import Union

from box import Box

from lazyft import logger
from lazyft.config import Config
from lazyft.pairlist import Pairlist
from lazyft.quicktools import QuickTools

logger = logger.getChild("hyperopt.commands")

command_map = dict(
    strategy='-s',
    config='-c',
    secret_config='-c',
    interval='-i',
    epochs='-e',
    min_trades='--min-trades',
    spaces='--spaces',
    loss='--hyperopt-loss',
    days='--days',
    timerange='--timerange',
    pairs='--pairs',
    starting_balance='--starting-balance',
    max_open_trades='--max-open-trades',
    stake_amount='--stake-amount',
    seed='--random-state',
)


class HyperoptCommand:
    def __init__(
        self,
        command_dict: dict[str, Union[str, list, int, float]],
        config: Config,
        strategy: str,
        secret_config: Config = None,
        id=None,
        pairs=None,
        verbose: bool = False,
    ) -> None:
        self.command_dict = Box(command_dict, default_box=True, default_box_attr=None)
        self.config = config
        self.strategy = strategy
        self.verbose = verbose
        self.secret_config = secret_config
        self.pairs = pairs
        self.id = id
        self.command_dict['config'] = self.config
        self.command_dict['pairs'] = pairs
        self.command_dict['strategy'] = strategy
        if self.secret_config:
            self.command_dict['secret_config'] = self.secret_config
        if id and not self.pairs:
            # load pairs from ID if pairs not already provided.
            self.pairs = Pairlist.load_from_id(strategy=strategy, id=id)

    @property
    def command_string(self):
        return self.build_command()

    def build_command(self):
        cd = self.command_dict.copy()
        assert cd.days or cd.timerange, "--days or --timerange must be specified"

        args = ['hyperopt']
        if not cd.timerange:
            cd.timerange, _ = QuickTools.get_timerange(
                self.config, cd.days, cd.interval
            )
            del cd.days

        for key, value in cd.items():
            if not value:
                continue
            if key == 'pairs':
                value = ' '.join(value)
            arg_line = f"{command_map[key]} {value}"
            args.append(arg_line)
        return ' '.join(args)


def create_commands(
    strategies: list[str],
    config: Union[str, pathlib.Path] = "config.json",
    secret_config: Union[pathlib.Path, str] = None,
    pairs: str = None,
    verbose=False,
    skip_data_download=False,
    **kwargs,
):
    """

    Args:
        strategies:
        config:
        secret_config:
        pairs:
        verbose:
        skip_data_download:
    Returns:
    """
    """Create `HyperoptCommand` for each strategy in strategies."""
    strategy_id_pair = []
    for s in strategies:
        if '-' in s:
            strategy_id_pair.append((tuple(s.split('-'))))
        else:
            strategy_id_pair.append((s, ''))
    if 'loss' not in kwargs:
        kwargs['loss'] = 'SortinoHyperOptLossDaily'
    if 'interval' not in kwargs:
        kwargs['interval'] = '5m'
    args = Box(kwargs, default_box=True, default_box_attr=None)
    logger.debug('creating commands for %s', strategies)
    logger.debug('args: %s', args)
    config = Config(config)
    if secret_config:
        secret_config = Config(secret_config)
    if not skip_data_download:
        QuickTools.download_data(
            config,
            interval=args.interval,
            days=args.days,
            timerange=args.timerange,
            verbose=verbose,
        )
    commands = []
    for s, id in strategy_id_pair:
        command = HyperoptCommand(
            command_dict=args,
            config=config,
            strategy=s,
            secret_config=secret_config,
            pairs=pairs,
            verbose=verbose,
            id=id,
        )
        command.build_command()
        commands.append(command)
    return commands
