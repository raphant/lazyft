import hashlib

import rapidjson
from loguru import logger


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
    def set_params_file(cls, strategy: str, id: str):
        """Load strategy parameters from a saved report."""

        from lazyft import paths
        from lazyft.strategy import StrategyTools

        parameters = cls.get_parameters(id)
        logger.debug('fetched parameters: {}', parameters)
        # get full name that the params file will be saved as
        strategy_json = StrategyTools.create_strategy_params_filepath(strategy)
        # setup the file path
        new_params_file = paths.STRATEGY_DIR.joinpath(strategy_json)
        # write into the new params file
        new_params_file.write_text(rapidjson.dumps(parameters))
        logger.info('Created parameter file {} with id {}', strategy_json, id)

    @classmethod
    def get_parameters(cls, id: str) -> dict:
        from lazyft.reports import get_hyperopt_repo

        return get_hyperopt_repo().get_by_param_id(id).parameters

    @classmethod
    def remove_params_file(cls, strategy) -> None:
        """
        Remove the params file for the given strategy.
        """

        from lazyft.strategy import StrategyTools

        filepath = StrategyTools.create_strategy_params_filepath(strategy)
        logger.info('Removing strategy params: {}', filepath)
        filepath.unlink(missing_ok=True)
