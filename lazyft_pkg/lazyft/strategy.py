import os
from pathlib import Path
from typing import Union

import sh
from freqtrade.configuration import Configuration
from freqtrade.optimize.hyperopt_tools import HyperoptTools
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import IStrategy

import lazyft.paths as paths
from lazyft import logger
from lazyft.config import Config
from lazyft.regex import strategy_files_pattern


class StrategyTools:
    strategy_dict = None
    _last_strategy_len = None


def get_name_from_id(id: int) -> str:
    from lazyft.reports import get_hyperopt_repo

    return get_hyperopt_repo().get_by_param_id(id).strategy


def create_strategy_params_filepath(strategy: str) -> Path:
    """Return the path to the strategies parameter file."""
    logger.debug('Getting parameters path of {}', strategy)
    file_name = get_file_name(strategy)
    if not file_name:
        raise ValueError("Could not find strategy: %s" % strategy)
    return paths.STRATEGY_DIR.joinpath(file_name.replace(".py", "") + ".json")


def get_strategy_param_path(strategy: str, config: Union[str, Path]) -> Path:
    if isinstance(config, Path):
        config = str(config)
    return paths.STRATEGY_DIR / HyperoptTools.get_strategy_filename(
        Configuration.from_files([config]), strategy
    ).with_suffix(".json")


def get_all_strategies():
    if StrategyTools.strategy_dict and StrategyTools._last_strategy_len == len(
        os.listdir(paths.STRATEGY_DIR)
    ):
        return StrategyTools.strategy_dict
    logger.info('Running list-strategies')
    text = sh.freqtrade(
        "list-strategies",
        no_color=True,
        userdir=str(paths.USER_DATA_DIR),
        # _out=lambda l: logger_exec.info(l.strip()),
        # _err=lambda l: logger_exec.info(l.strip()),
    )
    strat_dict = dict(strategy_files_pattern.findall("\n".join(text)))
    StrategyTools.strategy_dict = strat_dict
    StrategyTools._last_strategy_len = len(os.listdir(paths.STRATEGY_DIR))
    return strat_dict


def get_file_name(strategy: str) -> str:
    """Returns the file name of a strategy"""
    to_dict = get_all_strategies()
    return to_dict.get(strategy)


def load_strategy(strategy: str, config: Union[str, Config]) -> IStrategy:
    if isinstance(config, str):
        config = Config(config)
    config = Configuration.from_files([config.path])
    config["strategy"] = strategy
    return StrategyResolver.load_strategy(config)


def load_intervals_from_strategy(
    strategy: str, config: Union[str, Config], pairs: list = None
) -> str:
    """
    Loads the intervals from a strategy

    :param strategy: strategy name
    :param config: config file
    :param pairs: Use this list of pairs to simulate the DataProvider's whitelist
    :return: a list of intervals e.g. ['1m', '5m']

    """
    strategy = load_strategy(strategy, config)

    class Dp:
        @staticmethod
        def current_whitelist():
            return pairs or config.whitelist

    strategy.dp = Dp

    pairs = strategy.informative_pairs()
    return ' '.join(set([tf for pair, tf in pairs] + [strategy.timeframe]))


if __name__ == "__main__":
    print(load_intervals_from_strategy('Gumbo3', 'config.json', ['BTC/USDT']))
