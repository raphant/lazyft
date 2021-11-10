import datetime
from typing import Union

import attr

from lazyft.config import Config
from lazyft.ensemble import set_ensemble_strategies
from lazyft.models import Strategy
from lazyft.quicktools import QuickTools


def format_config(config_name: str):
    if not config_name:
        return
    return str(Config(str(config_name)))


def get_strategy_id_pairs(strategies: list[str]):
    pairs = []
    for s in strategies:
        if isinstance(s, Strategy):
            pairs.append(s.as_pair)
        elif '-' in s:
            pairs.append((tuple(s.split('-', 1))))
        else:
            pairs.append((s, ''))
    return pairs


def pairs_to_strategy(pairs: list[str]):
    strategies = []
    for p in pairs:
        if isinstance(p, Strategy):
            strategies.append(p)
            continue
        strategies.append(Strategy(*p.split('-', 1)))
    return strategies


@attr.s
class GlobalParameters:
    config_path: str = attr.ib(converter=format_config, metadata={'arg': '-c'})
    secrets_config: str = attr.ib(
        default=None, converter=format_config, metadata={'arg': '-c'}
    )
    strategies: list[Union[Strategy, str]] = attr.ib(default=None)
    download_data: bool = attr.ib(default=True)
    ensemble: list[Union[Strategy, str]] = attr.ib(
        default=[],
        converter=lambda s: set_ensemble_strategies(pairs_to_strategy(s or [])),
    )

    @property
    def config(self) -> Config:
        return Config(self.config_path)

    @property
    def strategy_id_pairs(self) -> list[tuple[str, ...]]:
        return get_strategy_id_pairs(self.strategies)


@attr.s
class BacktestParameters(GlobalParameters):
    timerange = attr.ib(default='', metadata={'arg': '--timerange'})
    pairs: list[str] = attr.ib(default=None, metadata={'arg': '--pairs'})
    days: int = attr.ib(default=45, metadata={'arg': '--days'})
    starting_balance: float = attr.ib(
        default=500, metadata={'arg': '--starting-balance'}
    )
    stake_amount: Union[float, str] = attr.ib(
        default='unlimited', metadata={'arg': '--stake-amount'}
    )
    max_open_trades: int = attr.ib(default=5, metadata={'arg': '--max-open-trades'})
    interval: str = attr.ib(default='5m', metadata={'arg': '-i'})
    inf_interval: str = attr.ib(default='')
    tag: str = attr.ib(default='')

    def __attrs_post_init__(self):
        if not self.timerange:
            self.timerange = QuickTools.get_timerange(days=self.days)[1]
        if not self.tag:
            open_, close = self.timerange.split('-')
            if not close:
                close = datetime.datetime.now().strftime('%Y%m%d')
            self.tag = f'{open_}-{close}'
        if not self.pairs:
            self.pairs = self.config.whitelist

    @property
    def intervals_to_download(self):
        intervals = self.interval
        if self.inf_interval:
            intervals += ' ' + self.inf_interval
        return intervals


@attr.s
class HyperoptParameters(BacktestParameters):
    epochs: int = attr.ib(default=500, metadata={'arg': '-e'})
    min_trades: int = attr.ib(default=100, metadata={'arg': '--min-trades'})
    spaces: str = attr.ib(default='default', metadata={'arg': '--spaces'})
    loss: str = attr.ib(
        default='WinRatioAndProfitRatioLoss', metadata={'arg': '--hyperopt-loss'}
    )
    seed: int = attr.ib(default=None, metadata={'arg': '--random-state'})
    jobs: int = attr.ib(default=-1, metadata={'arg': '-j'})
    print_all: bool = attr.ib(default=False, metadata={'arg': '--print-all'})

    def __attrs_post_init__(self):
        if not self.timerange:
            self.timerange = QuickTools.get_timerange(days=self.days)[0]
        if not self.tag:
            self.tag = self.timerange + ',' + self.spaces
        if not self.pairs:
            self.pairs = self.config.whitelist


command_map = {
    a.name: a.metadata.get('arg') for a in attr.fields(HyperoptParameters) if a.metadata
}
