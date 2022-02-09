import os
import shutil
import tempfile
from pathlib import Path
from typing import Union, TYPE_CHECKING

import sh
from freqtrade.configuration import Configuration
from freqtrade.optimize.hyperopt_tools import HyperoptTools
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import IStrategy

import lazyft.paths as paths
from lazyft import logger, util, parameter_tools
from lazyft.config import Config
from lazyft.regex import strategy_files_pattern

if TYPE_CHECKING:
    from lazyft.command_parameters import BacktestParameters
    from lazyft.models import StrategyBackup


class StrategyTools:
    strategy_dict = None
    _last_strategy_len = None


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
        'create_strategy_params_filepath is deprecated. Use get_strategy_param_path instead.'
    )
    logger.debug('Getting parameters path of {}', strategy)
    file_name = get_file_name(strategy)
    if not file_name:
        raise ValueError('Could not find strategy: %s' % strategy)
    return paths.STRATEGY_DIR.joinpath(file_name.replace('.py', '') + '.json')


def get_strategy_param_path(
    strategy: str, config: Union[str, Path] = paths.CONFIG_DIR.joinpath('config.json')
) -> Path:
    if isinstance(config, Path):
        config = str(config)
    return paths.STRATEGY_DIR / HyperoptTools.get_strategy_filename(
        Configuration.from_files([config]), strategy
    ).with_suffix('.json')


def get_all_strategies():
    if StrategyTools.strategy_dict and StrategyTools._last_strategy_len == len(
        os.listdir(paths.STRATEGY_DIR)
    ):
        return StrategyTools.strategy_dict
    # logger.info('Running list-strategies')
    text = sh.freqtrade(
        "list-strategies",
        no_color=True,
        userdir=str(paths.USER_DATA_DIR),
        # _out=lambda l: logger_exec.info(l.strip()),
        # _err=lambda l: logger_exec.info(l.strip()),
    )
    strat_dict = dict(strategy_files_pattern.findall('\n'.join(text)))
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


def load_intervals_from_strategy(strategy_name: str, parameters: 'BacktestParameters') -> str:
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
    intervals = ' '.join([t for t in tfs if t])
    logger.debug('Intervals for strategy {}: {}', strategy_name, intervals)
    return intervals


def load_informative_intervals_and_pairs_from_strategy(
    strategy_name: str, parameters: 'BacktestParameters'
) -> tuple[list[str], list[str]]:
    args = parameters.to_config_dict(strategy_name)
    strategy = StrategyResolver.load_strategy(args)

    class Dp:
        @staticmethod
        def current_whitelist():
            return parameters.pairs

    strategy.dp = Dp

    inf_pairs = strategy.informative_pairs()
    tfs = set([tf for pair, tf in inf_pairs] + [strategy.timeframe])
    if parameters.timeframe_detail:
        tfs.add(parameters.timeframe_detail)
    inf_pairs = set([pair for pair, tf in inf_pairs])
    # get difference inf_pairs and pairs
    pairs = inf_pairs - set(parameters.pairs)
    return list(tfs), list(pairs)


def save_strategy_text_to_database(strategy_name: str) -> str:
    """
    Save the strategy text to the database

    :param strategy_name: strategy name
    :return: The hash of the strategy text
    """
    from lazyft.models import StrategyBackup

    strategy_path = paths.STRATEGY_DIR / get_file_name(strategy_name)
    # create a hash
    text = strategy_path.read_text()
    hash = util.hash(text)
    # check if strategy is already in database
    existing_backup = StrategyBackup.load_hash(hash)
    if existing_backup:
        logger.info(f'Strategy {strategy_name} already in database...skipping')
        return hash
    StrategyBackup(name=strategy_name, text=text, hash=hash).save()
    logger.info(f'Saved strategy {strategy_name} with hash {hash} to database')
    return hash


def create_temp_folder_for_strategy_and_params_from_backup(
    strategy_backup: 'StrategyBackup', hyperopt_id: int = None
) -> Path:
    """
    Creates a temporary folder that FreqTrade will run a backed-up strategy. If a hyperopt_id is
    provided, the parameters of the id will be loaded and exported to the same folder.

    :param strategy_backup: The strategy backup to load the strategy from
    :param hyperopt_id: The hyperopt parameters to load and save to the json file
    :return: The path to the new folder
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix=f'lazyft-{strategy_backup.name}_'))
    logger.info(f'Created temporary folder {tmp_dir} for strategy backup {strategy_backup.name}')
    path = strategy_backup.export_to(tmp_dir)
    logger.info(f'Exported strategy backup {strategy_backup.name} to {path}')
    if hyperopt_id:
        parameter_tools.set_params_file(hyperopt_id, export_path=path.with_suffix('.json'))
    hyperopt_data_dir = paths.USER_DATA_DIR / 'hyperopt_results'
    # backtest_data_dir = paths.USER_DATA_DIR / 'backtest_results'
    # create a link in tmp folder to hyperopt_data_dir and backtest_data_dir
    os.symlink(str(hyperopt_data_dir.resolve()), str((tmp_dir / 'hyperopt_results/').resolve()))
    # create a link in tmp folder to the data dir
    os.symlink(
        str(paths.USER_DATA_DIR.joinpath('data').resolve()), str((tmp_dir / 'data/').resolve())
    )
    logger.info(f'Created symlink to hyperopt_data_dir and data in {tmp_dir}')
    return tmp_dir


def delete_temporary_strategy_backup_dir(tmp_dir: Path) -> None:
    """
    Deletes the temporary strategy backup folder

    :param tmp_dir: The temporary strategy backup folder
    :return: None
    """
    if tmp_dir and tmp_dir.exists():
        logger.info(f'Deleting temporary strategy folder {tmp_dir}')
        shutil.rmtree(tmp_dir)
    else:
        logger.info(f'Temporary folder "{tmp_dir}" does not exist...skipping')


if __name__ == "__main__":
    from lazyft.command_parameters import BacktestParameters

    b_params = BacktestParameters(
        pairs=['ETH/BTC'],
        config_path=paths.CONFIG_DIR / "config.json",
    )
    print(load_intervals_from_strategy('Gumbo3', b_params))
