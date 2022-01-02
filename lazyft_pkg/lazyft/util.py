import hashlib
from datetime import timedelta, datetime
from pathlib import Path
from typing import Union

from freqtrade.constants import LAST_BT_RESULT_FN
from freqtrade.misc import file_dump_json
from loguru import logger
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


class ParameterTools:
    @classmethod
    def set_params_file(cls, hyperopt_id: int):
        """Load strategy parameters from a saved report."""

        from lazyft.reports import get_hyperopt_repo

        report = get_hyperopt_repo().get(hyperopt_id)
        report.export_parameters()

    @classmethod
    def get_parameters(cls, id: str) -> dict:
        from lazyft.reports import get_hyperopt_repo

        return get_hyperopt_repo().get(id).parameters

    @classmethod
    def remove_params_file(cls, strategy, config: Union[str, Path] = None) -> None:
        """
        Remove the params file for the given strategy.
        """
        from lazyft.strategy import get_strategy_param_path
        from lazyft.config import Config

        if not config:
            config = Config('config.json')
        if isinstance(config, str):
            config = Path(config)
        filepath = get_strategy_param_path(strategy, str(config))
        logger.info('Removing strategy params: {}', filepath)
        filepath.unlink(missing_ok=True)


def hhmmss_to_seconds(timestamp: str):
    """
    Convert a timestamp in the format HH:MM:SS to seconds.
    """
    h, m, s = timestamp.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)


def get_last_hyperopt_file_path():
    from lazyft.paths import LAST_HYPEROPT_RESULTS_FILE
    import rapidjson

    return (
        LAST_HYPEROPT_RESULTS_FILE.parent
        / rapidjson.loads(LAST_HYPEROPT_RESULTS_FILE.read_text())['latest_hyperopt']
    )


def duration_string_to_timedelta(delta_string: str):
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
