from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from freqtrade.commands import Arguments
from freqtrade.configuration import Configuration, setup_utils_configuration
from freqtrade.constants import USERPATH_STRATEGIES
from freqtrade.data.dataprovider import DataProvider
from freqtrade.enums import RunMode
from freqtrade.optimize.hyperopt_tools import HyperoptTools
from freqtrade.resolvers import ExchangeResolver, StrategyResolver
from freqtrade.strategy import IStrategy
from freqtrade.strategy.informative_decorator import InformativeData

import lazyft.paths as paths
from lazyft import BASIC_CONFIG, logger, parameter_tools, util
from lazyft.config import Config
from lazyft.space_handler import SpaceHandler

if TYPE_CHECKING:
    from lazyft.command_parameters import BacktestParameters
    from lazyft.models import StrategyBackup


class StrategyTools:
    strategy_dict = None
    _last_strategy_len = None


def start_list_strategies(args: dict[str, Any]):
    """
    Return files with Strategy custom classes available in the directory
    """
    config = setup_utils_configuration(args, RunMode.UTIL_NO_EXCHANGE)

    directory = Path(
        config.get("strategy_path", config["user_data_dir"] / USERPATH_STRATEGIES)
    )
    strategy_objs = StrategyResolver.search_all_objects(
        directory, not args["print_one_column"]
    )
    # Sort alphabetically
    strategy_objs = sorted(strategy_objs, key=lambda x: x["name"])
    for obj in strategy_objs:
        if obj["class"]:
            obj["hyperoptable"] = obj["class"].detect_all_parameters()
        else:
            obj["hyperoptable"] = {"count": 0}
    return strategy_objs


def get_name_from_id(id: int) -> str:
    from lazyft.reports import get_hyperopt_repo

    return get_hyperopt_repo().get_by_param_id(id).strategy


def create_strategy_params_filepath(strategy: str) -> Path:
    """
    Creates a strategy params file path (LEGACY)
    :param strategy:
    :return:
    """
    """Return the path to the strategies parameter file."""
    logger.warning(
        "create_strategy_params_filepath is deprecated. Use get_strategy_param_path instead."
    )
    logger.debug("Getting parameters path of {}", strategy)
    file_name = get_file_name(strategy)
    if not file_name:
        raise ValueError("Could not find strategy: %s" % strategy)
    return paths.STRATEGY_DIR.joinpath(file_name.replace(".py", "") + ".json")


def get_strategy_param_path(
    strategy: str, config: Union[str, Path] = paths.CONFIG_DIR.joinpath("config.json")
) -> Path:
    if isinstance(config, Path):
        config = str(config)
    return paths.STRATEGY_DIR / HyperoptTools.get_strategy_filename(
        Configuration.from_files([config]), strategy
    ).with_suffix(".json")


def get_all_strategies() -> dict[str, dict]:
    """
    Returns a dict of all strategies
    :return: A dict of dicts with the following keys: name, class, location, hyperoptable.
    """
    cli = f"list-strategies --no-color --userdir {paths.USER_DATA_DIR}"
    args = Arguments(cli.split()).get_parsed_arg()

    strats = start_list_strategies(args)
    # pop 'name' key of each dict in strats and make it the key
    return {strat["name"]: strat for strat in strats}


def get_file_name(strategy: str) -> str:
    """Returns the file name of a strategy"""
    get = get_all_strategies().get(strategy)
    assert get, f"Could not find strategy: {strategy}"
    return get["location"].name


def load_strategy(strategy: str, config: Union[str, Config, dict]) -> IStrategy:
    """
    Loads a strategy from a config file

    :param strategy: The name of the strategy class to be loaded
    :type strategy: str
    :param config: The configuration object
    :type config: Union[str, Config]
    :return: An instance of the IStrategy class.
    """
    if isinstance(config, str):
        config = Configuration.from_files([config])
    elif isinstance(config, Config):
        config = Configuration.from_files([config.path])
    assert isinstance(config, dict), "Invalid config type"
    config["strategy"] = strategy
    exchange = ExchangeResolver.load_exchange(config["exchange"]["name"], config)
    dataprovider = DataProvider(config, exchange)
    load_strategy = StrategyResolver.load_strategy(config)
    load_strategy.dp = dataprovider
    return load_strategy


def load_intervals_from_strategy(
    strategy_name: str, parameters: "BacktestParameters"
) -> str:
    """
    Loads the intervals from a strategy

    :param strategy_name: strategy name
    :param parameters: global parameters
    :return: a list of intervals e.g. ['1m', '5m']

    """
    args = parameters.to_config_dict(strategy_name)
    strategy = StrategyResolver.load_strategy(args)

    class Dp:
        @staticmethod
        def current_whitelist():
            return parameters.pairs

    strategy.dp = Dp

    inf_pairs = strategy.informative_pairs()
    tfs = set([tf for pair, tf in inf_pairs])
    tfs.add(parameters.timeframe_detail)
    tfs.add(strategy.timeframe)
    intervals = " ".join([t for t in tfs if t])
    logger.debug("Intervals for strategy {}: {}", strategy_name, intervals)
    return intervals


def load_informative_intervals_and_pairs_from_strategy(
    config: Union[str, Config, dict], pairs, timeframe_detail=None
) -> tuple[list[str], list[str]]:
    strategy = load_strategy(config["strategy"], config)

    class Dp:
        @staticmethod
        def current_whitelist():
            return pairs

    strategy.dp = Dp
    inf_pairs = strategy.informative_pairs()
    tfs = set([tf for pair, tf in inf_pairs] + [strategy.timeframe])
    if timeframe_detail:
        tfs.add(timeframe_detail)
    inf_pairs = set([pair for pair, tf in inf_pairs])
    for dec in strategy._ft_informative:
        obj: InformativeData = dec[0]
        tfs.add(obj.timeframe)
        if "{stake}" in obj.asset:
            inf_pairs.add(obj.asset.format(stake=strategy.stake_currency))
    # get difference inf_pairs and pairs
    new_pairs = set(list(inf_pairs) + pairs)
    return list(tfs), list(new_pairs)


def save_strategy_text_to_database(strategy_name: str) -> str:
    """
    Save the strategy text to the database

    :param strategy_name: strategy name
    :return: The hash of the strategy text
    """
    from lazyft.models import StrategyBackup

    hash, text = get_strategy_hash_and_text(strategy_name)
    # check if strategy is already in database
    existing_backup = StrategyBackup.load_hash(hash)
    if existing_backup:
        logger.info(f"Strategy {strategy_name} already in database...skipping")
        return hash
    StrategyBackup(name=strategy_name, text=text, hash=hash).save()
    logger.info(f"Saved strategy {strategy_name} with hash {hash} to database")
    return hash


def get_strategy_hash_and_text(strategy_name):
    strategy_path = paths.STRATEGY_DIR / get_file_name(strategy_name)
    # create a hash
    text = strategy_path.read_text()
    hash = util.hash(text)
    return hash, text


def create_temp_folder_for_strategy_and_params_from_backup(
    strategy_backup: "StrategyBackup", hyperopt_id: int = None
) -> Path:
    """
    Creates a temporary folder that FreqTrade will run a backed-up strategy. If a hyperopt_id is
    provided, the parameters of the id will be loaded and exported to the same folder.

    :param strategy_backup: The strategy backup to load the strategy from
    :param hyperopt_id: The hyperopt parameters to load and save to the json file
    :return: The path to the new folder
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"lazyft-{strategy_backup.name}_"))
    logger.info(
        f"Created temporary folder {tmp_dir} for strategy backup {strategy_backup.name}"
    )
    path = strategy_backup.export_to(tmp_dir)
    logger.info(f"Exported strategy backup {strategy_backup.name} to {path}")
    if hyperopt_id:
        parameter_tools.set_params_file(
            hyperopt_id, export_path=path.with_suffix(".json")
        )
    hyperopt_data_dir = paths.USER_DATA_DIR / "hyperopt_results"
    backtest_data_dir = paths.USER_DATA_DIR / "backtest_results"
    # backtest_data_dir = paths.USER_DATA_DIR / 'backtest_results'
    # create a link in tmp folder to hyperopt_data_dir and backtest_data_dir
    os.symlink(
        str(hyperopt_data_dir.resolve()), str((tmp_dir / "hyperopt_results/").resolve())
    )
    os.symlink(
        str(backtest_data_dir.resolve()), str((tmp_dir / "backtest_results/").resolve())
    )
    # create a link in tmp folder to the data dir
    os.symlink(
        str(paths.USER_DATA_DIR.joinpath("data").resolve()),
        str((tmp_dir / "data/").resolve()),
    )
    logger.info(
        f"Created user_data symlink's to hyperopt_results, backtest_results, and data in {tmp_dir}"
    )
    return tmp_dir


def delete_temporary_strategy_backup_dir(tmp_dir: Path) -> None:
    """
    Deletes the temporary strategy backup folder

    :param tmp_dir: The temporary strategy backup folder
    :return: None
    """
    if tmp_dir and tmp_dir.exists():
        logger.info(f"Deleting temporary strategy folder {tmp_dir}")
        shutil.rmtree(tmp_dir)
    else:
        logger.info(f'Temporary folder "{tmp_dir}" does not exist...skipping')


def get_space_handler_spaces(strategy_name: str) -> set[str]:
    """
    Get the hyperopt space for a strategy

    :param strategy_name: The strategy name
    :return: The hyperopt space
    """
    config = BASIC_CONFIG
    config["strategy"] = strategy_name
    strategy = StrategyResolver.load_strategy(config)
    sh: Optional[SpaceHandler] = getattr(strategy, "sh", None)
    if not sh:
        raise ValueError(f"Strategy {strategy_name} has no space handler")
    return sh.attempted_loads


def clear_spaces(strategy_name: str) -> None:
    config = BASIC_CONFIG
    config["strategy"] = strategy_name
    sh = SpaceHandler(paths.STRATEGY_DIR / get_file_name(strategy_name))
    if not sh:
        raise ValueError(f"Strategy {strategy_name} has no space handler")
    sh.reset()
    sh.save()


if __name__ == "__main__":
    # from lazyft.command_parameters import BacktestParameters

    # b_params = BacktestParameters(
    #     pairs=['ETH/BTC'],
    #     config_path=paths.CONFIG_DIR / "config.json",
    # )
    # print(load_intervals_from_strategy('Gumbo3', b_params))
    print(get_space_handler_spaces("ClucHAnix_BB_RPB_MOD"))
