from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
from typing import Any, Union

import attr
import lazyft.paths
from freqtrade.commands import Arguments
from freqtrade.configuration import Configuration
from freqtrade.exceptions import OperationalException
from freqtrade.loggers import LOGFORMAT, bufferHandler, setup_logging_pre
from lazyft import logger, parameter_tools
from lazyft.config import Config
from lazyft.ensemble import set_ensemble_strategies
from lazyft.models import Strategy
from lazyft.util import get_timerange


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
    command = ''
    config_path: Union[str, Config] = attr.ib(converter=format_config, metadata={'arg': '-c'})
    secrets_config: Union[str, Config] = attr.ib(
        default=None, converter=format_config, metadata={'arg': '-c'}
    )
    logfile: str = attr.ib(default=None, metadata={'arg': '--logfile'})
    strategies: list[Union[Strategy, str]] = attr.ib(default=None)
    download_data: bool = attr.ib(default=True)
    user_data_dir: Path = attr.ib(
        default=lazyft.paths.USER_DATA_DIR, metadata={'arg': '--user-data-dir'}
    )
    extra_args: str = attr.ib(default='')
    # data_dir: Path = attr.ib(
    #     default=lazyft.paths.USER_DATA_DIR / 'data', metadata={'arg': '--datadir'}
    # )
    strategy_path: Path = attr.ib(
        default=lazyft.paths.USER_DATA_DIR / 'strategies', metadata={'arg': '--strategy-path'}
    )

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

    @property
    def command_string(self) -> str:
        args = [self.command]

        for key, value in self.__dict__.items():
            if not value or key not in command_map or key == 'days':
                continue
            if value is True:
                value = ''
            if key == 'pairs':
                value = ' '.join(value)
            arg_line = f"{command_map[key]} {value}".strip()
            args.append(arg_line)
        if self.extra_args:
            args.append(self.extra_args)
        return ' '.join(args)

    def to_config_dict(self, strategy_name: str) -> dict[str, Any]:
        args = Arguments(self.command_string.split()).get_parsed_arg()
        args['strategy'] = strategy_name
        return Configuration(args).get_config()


def enable_ft_logging():
    logging.basicConfig(
        level=logging.INFO,
        format=LOGFORMAT,
        handlers=[logging.StreamHandler(sys.stderr), bufferHandler],
    )


@attr.s
class BacktestParameters(GlobalParameters):
    command = 'backtesting'
    timerange = attr.ib(default='', metadata={'arg': '--timerange'})
    pairs: list[str] = attr.ib(factory=list, metadata={'arg': '--pairs'})
    days: int = attr.ib(default=60, metadata={'arg': '--days'})
    starting_balance: float = attr.ib(default=500, metadata={'arg': '--starting-balance'})
    stake_amount: Union[float, str] = attr.ib(
        default='unlimited', metadata={'arg': '--stake-amount'}
    )
    max_open_trades: int = attr.ib(default=5, metadata={'arg': '--max-open-trades'})
    interval: str = attr.ib(default='', metadata={'arg': '--timeframe'})
    timeframe_detail: str = attr.ib(default='', metadata={'arg': '--timeframe-detail'})
    cache: str = attr.ib(default='none', metadata={'arg': '--cache'})
    inf_interval: str = attr.ib(default='')
    tag: str = attr.ib(default='')
    custom_spaces: str = attr.ib(default='')
    custom_settings: dict = attr.ib(factory=dict)

    def __attrs_post_init__(self):
        if not self.timerange:
            self.timerange = get_timerange(days=self.days)[1]
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
            intervals += ' ' + self.inf_interval + ' ' + self.timeframe_detail
        return intervals

    def run(
        self, strategy: Union[str, Strategy], load_from_hash=False, verbose=False, stdout=False
    ):
        from lazyft.backtest import commands
        from lazyft.backtest.runner import BacktestRunner

        if isinstance(strategy, str):
            try:
                s, id = strategy.split('-', 1)
            except ValueError:
                s, id = strategy, ''
            strategy = Strategy(s, id)

        if not self.interval:
            strategy.args = self.to_config_dict(strategy.name)
            try:
                self.interval = strategy.as_ft_strategy.timeframe
            except OperationalException as e:
                # if the msg == "Invalid parameter file provided", delete parameter file and retry
                if 'Invalid parameter file provided' in str(e):
                    print(self.config_path)
                    parameter_tools.remove_params_file(strategy.name, self.config.path)
                    self.interval = strategy.as_ft_strategy.timeframe

        command = commands.BacktestCommand(
            strategy.name,
            params=self,
            verbose=verbose,
            id=strategy.id,
        )
        if stdout:
            enable_ft_logging()
        runner = BacktestRunner(command, load_from_hash=load_from_hash)
        try:
            runner.execute()
        except Exception as e:
            logger.exception(e)
        return runner

    def run_multiple(self, *strategies: Union[str, Strategy], verbose=False):
        raise NotImplementedError


@attr.s
class HyperoptParameters(BacktestParameters):
    command = 'hyperopt'
    epochs: int = attr.ib(default=500, metadata={'arg': '--epochs'})
    min_trades: int = attr.ib(default=100, metadata={'arg': '--min-trades'})
    spaces: str = attr.ib(default='default', metadata={'arg': '--spaces'})
    loss: str = attr.ib(default='WinRatioAndProfitRatioLoss', metadata={'arg': '--hyperopt-loss'})
    seed: int = attr.ib(default=None, metadata={'arg': '--random-state'})
    jobs: int = attr.ib(default=-1, metadata={'arg': '--job-workers'})
    disable_param_export: bool = attr.ib(default=True, metadata={'arg': '--disable-param-export'})
    print_all: bool = attr.ib(default=False, metadata={'arg': '--print-all'})
    ignore_missing_spaces: bool = attr.ib(default=True, metadata={'arg': '--ignore-missing-spaces'})
    cache: str = None

    def __attrs_post_init__(self):
        if not self.timerange:
            self.timerange = get_timerange(days=self.days)[0]
        if not self.tag:
            self.tag = self.timerange + ',' + self.spaces
        if not self.pairs:
            self.pairs = self.config.whitelist
        del self.cache

    def run(
        self,
        strategy: Union[Strategy, str],
        autosave=False,
        notify=False,
        verbose=False,
        background=False,
        load_hashed_strategy=False,
    ):
        from lazyft.hyperopt import commands
        from lazyft.hyperopt.runner import HyperoptRunner

        if isinstance(strategy, str):
            try:
                s, id = strategy.split('-', 1)
            except ValueError:
                s, id = strategy, ''
            strategy = Strategy(s, id)
        # if not self.interval:
        #     strategy.args = self.to_config_dict(strategy.name)
        #     try:
        #         self.interval = strategy.as_ft_strategy.timeframe
        #     except OperationalException as e:
        #         # if the msg == "Invalid parameter file provided", delete parameter file and retry
        #         if 'Invalid parameter file provided' in str(e):
        #             parameter_tools.remove_params_file(strategy.name, self.config.path)
        #             self.interval = strategy.as_ft_strategy.timeframe
        command = commands.HyperoptCommand(
            strategy.name,
            params=self,
            id=strategy.id,
            verbose=verbose,
        )
        runner = HyperoptRunner(command, autosave=autosave, notify=notify, verbose=verbose)

        try:
            runner.execute(background=background, load_strategy=load_hashed_strategy)
        except Exception as e:
            logger.exception(e)
        return runner

    def run_multiple(self, *strategies: Union[str, Strategy], verbose=False):
        pass


command_map = {a.name: a.metadata.get('arg') for a in attr.fields(HyperoptParameters) if a.metadata}
