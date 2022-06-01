from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Tuple, Union

import rapidjson
from diskcache import Index
from freqtrade.commands import Arguments
from freqtrade.configuration import setup_utils_configuration
from freqtrade.constants import LAST_BT_RESULT_FN
from freqtrade.data.btanalysis import get_latest_hyperopt_file
from freqtrade.enums import RunMode
from freqtrade.misc import file_dump_json
from pandas import DataFrame


def hash(obj):
    """
    Since hash() is not guaranteed to give the same result in different
    sessions, we will be using hashlib for more consistent hash_ids
    """
    if isinstance(obj, (set, tuple, list, dict)):
        obj = repr(obj)
    hash_id = hashlib.md5()
    hash_id.update(repr(obj).encode('utf-8'))
    hex_digest = str(hash_id.hexdigest())
    return hex_digest


def human_format(num):
    if num < 1000:
        return f'{num:,.3f}'
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format(
        '{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude]
    )


def hhmmss_to_seconds(timestamp: str):
    """
    Convert a timestamp in the format HH:MM:SS to seconds.
    """
    h, m, s = timestamp.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)


def get_last_hyperopt_file_name() -> str:
    """
    It reads the last hyperopt results file and returns the name of the latest hyperopt file
    :return: A string of the name of the latest hyperopt file.
    """
    from lazyft.paths import LAST_HYPEROPT_RESULTS_FILE

    return Path(
        LAST_HYPEROPT_RESULTS_FILE.parent
        / rapidjson.loads(LAST_HYPEROPT_RESULTS_FILE.read_text())['latest_hyperopt']
    ).name


def get_latest_backtest_filename() -> str:
    """
    Get the latest backtest filename
    :return: The filename of the latest backtest
    """
    from lazyft.paths import LAST_BACKTEST_RESULTS_FILE

    return Path(
        LAST_BACKTEST_RESULTS_FILE.parent
        / rapidjson.loads(LAST_BACKTEST_RESULTS_FILE.read_text())['latest_backtest']
    ).name


def duration_string_to_timedelta(delta_string: str):
    """
    Convert a string of the form "X days, HH:MM:SS" into a timedelta object

    :param delta_string: The string that you want to convert to a timedelta
    :type delta_string: str
    :return: A timedelta object.
    """
    # turn "2 days, HH:MM:SS" into a time delta
    if 'day' in delta_string:
        delta = timedelta(
            days=int(delta_string.split(' ')[0]),
            hours=int(delta_string.split(' ')[2].split(':')[0]),
            minutes=int(delta_string.split(' ')[2].split(':')[1]),
            seconds=int(delta_string.split(' ')[2].split(':')[2]),
        )
    else:
        # turn "HH:MM:SS" into a time delta
        delta = timedelta(
            hours=int(delta_string.split(':')[0]),
            minutes=int(delta_string.split(':')[1]),
            seconds=int(delta_string.split(':')[2]),
        )
    return delta


def store_backtest_stats(recordfilename: Path, stats: dict[str, DataFrame]) -> Path:
    """
    Stores backtest results

    :param recordfilename: Path object, which can either be a filename or a directory.
    Filenames will be appended with a timestamp right before the suffix
    while for directories, <directory>/backtest-result-<datetime>.json will be used as filename
    :param stats: Dataframe containing the backtesting statistics

    :return: Path object pointing to the file where the statistics were stored
    """
    if recordfilename.is_dir():
        filename = (
            recordfilename / f'backtest-result-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json'
        )
    else:
        filename = Path.joinpath(
            recordfilename.parent,
            f'{recordfilename.stem}-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}',
        ).with_suffix(recordfilename.suffix)
    file_dump_json(filename, stats)

    latest_filename = Path.joinpath(filename.parent, LAST_BT_RESULT_FN)
    file_dump_json(latest_filename, {'latest_backtest': str(filename.name)})
    return filename


def get_best_hyperopt() -> int:
    """
    It returns the index of the best hyperopt result in the list of all hyperopt results

    :return: The index of the best hyperopt result.
    """
    command_best = 'hyperopt-show --best'.split()
    command_all = 'hyperopt-show'.split()
    args_best = Arguments(command_best).get_parsed_arg()
    args_all = Arguments(command_all).get_parsed_arg()

    from freqtrade.optimize.hyperopt_tools import HyperoptTools

    config_best = setup_utils_configuration(args_best, RunMode.UTIL_NO_EXCHANGE)
    config_all = setup_utils_configuration(args_all, RunMode.UTIL_NO_EXCHANGE)

    results_file_best = get_latest_hyperopt_file(
        config_best['user_data_dir'] / 'hyperopt_results', config_best.get('hyperoptexportfilename')
    )
    results_file_all = get_latest_hyperopt_file(
        config_all['user_data_dir'] / 'hyperopt_results', config_all.get('hyperoptexportfilename')
    )

    n = config_best.get('hyperopt_show_index', -1)

    # Previous evaluations
    epochs_all, _ = HyperoptTools.load_filtered_results(results_file_all, config_all)
    # Best evaluation
    epochs_best, _ = HyperoptTools.load_filtered_results(results_file_best, config_best)

    # Translate epoch index from human-readable format to pythonic
    if n > 0:
        n -= 1
    return epochs_all.index(epochs_best[n])


def get_timerange(days: int) -> Tuple[str, str]:
    """
    Get the timerange for the given number of days. The days will automatically be split into
    2/3rds for hyperopting and 1/3rd for backtesting.

    :param days: The number of days to get the timerange for
    :return: The hyperopt timerange and the backtesting timerange, respectively
    """
    today = datetime.now()
    start_day = datetime.now() - timedelta(days=days)
    hyperopt_days = round(days - days / 3)
    backtest_days = round(days / 3) - 1
    hyperopt_start, hyperopt_end = start_day, start_day + timedelta(days=hyperopt_days)
    backtest_start, backtest_end = (today - timedelta(days=backtest_days), today)

    hyperopt_range = f'{hyperopt_start.strftime("%Y%m%d")}-{hyperopt_end.strftime("%Y%m%d")}'
    backtest_range = f'{backtest_start.strftime("%Y%m%d")}-{backtest_end.strftime("%Y%m%d")}'
    return hyperopt_range, backtest_range


def dict_to_telegram_string(d: dict[str, Any]) -> str:
    """
    Converts a dictionary to a readable string

    :param d: The dictionary to convert
    :return: The string representation of the dictionary
    """
    new_dict = {}
    for k, v in d.items():
        # replace _ with spaces
        new_key = k.replace('_', ' ')
        if isinstance(v, datetime):
            new_val = v.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(v, float):
            new_val = f'{v:.3f}'
        else:
            new_val = v
        new_dict[new_key] = new_val
    if 'seed' in new_dict:
        del new_dict['seed']
    return '\n'.join([f'*{k.capitalize()}:* `{v}`' for k, v in new_dict.items()])


def calculate_win_ratio(wins, losses, draws):
    return int(wins) / (max(int(wins) + int(draws) + int(losses), 1))


def remove_cache(cache: Union[str, Path]) -> None:
    """
    Removes the given cache directory
    """
    if isinstance(cache, str):
        cache = Path(cache)
    if cache.is_dir():
        shutil.rmtree(cache)
