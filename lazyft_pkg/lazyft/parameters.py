from dataclasses import dataclass, field
from typing import Optional, Union

import attr

from lazyft.config import Config


def to_config(config_name: str):
    if not config_name:
        return
    return Config(config_name)


@attr.s
class GlobalParameters:
    strategies: list[str] = attr.ib()
    config: Union[Config, str] = attr.ib(converter=to_config, metadata={'arg': '-c'})
    secrets_config: str = attr.ib(default='', metadata={'arg': '-c'})

    @property
    def strategy_id_pairs(self) -> list[tuple[str, ...]]:
        pairs = []
        for s in self.strategies:
            if '-' in s:
                pairs.append((tuple(s.split('-'))))
            else:
                pairs.append((s, ''))
        return pairs


@attr.s
class CommandParameters(GlobalParameters):
    pairs: list[str] = attr.ib(default=None, metadata={'arg': '--pairs'})
    timerange: str = attr.ib(default='', metadata={'arg': '--timerange'})
    days: int = attr.ib(default=45, metadata={'arg': '--days'})
    starting_balance: float = attr.ib(
        default=500, metadata={'arg': '--starting-balance'}
    )
    stake_amount: Union[float, str] = attr.ib(
        default='unlimited', metadata={'arg': '--stake-amount'}
    )
    max_open_trades: int = attr.ib(default=5, metadata={'arg': '--max-open-trades'})
    interval: str = attr.ib(default='5m', metadata={'arg': '-i'})


@attr.s
class HyperoptParameters(CommandParameters):
    epochs: int = attr.ib(default=500, metadata={'arg': '-e'})
    min_trades: int = attr.ib(default=100, metadata={'arg': '--min-trades'})
    spaces: str = attr.ib(default='default', metadata={'arg': '--spaces'})
    loss: str = attr.ib(
        default='SortinoHyperOptLossDaily', metadata={'arg': '--hyperopt-loss'}
    )
    seed: int = attr.ib(default=None, metadata={'arg': '--random-state'})


command_map = {
    a.name: a.metadata.get('arg')
    for a in attr.fields(HyperoptParameters) + attr.fields(GlobalParameters)
    if a.metadata
}
