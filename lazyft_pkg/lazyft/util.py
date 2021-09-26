import hashlib
from pathlib import Path

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
        from lazyft import paths
        from lazyft.strategy import StrategyTools

        logger.info('Copying id file {}.json to strategy folder', id)
        """Load strategy parameters from a saved param export."""
        id_param_file = cls.get_path_of_params(id)
        if not id_param_file.exists():
            raise FileNotFoundError('%s does not exist.' % id_param_file)
        # get full name that the params file will be saved as
        strategy_json = StrategyTools.create_strategy_params_filepath(strategy)
        # setup the file path
        new_params_file = paths.STRATEGY_DIR.joinpath(strategy_json)
        # write into the new params file
        new_params_file.write_text(id_param_file.read_text())
        logger.debug('Finished copying {} -> {}', id_param_file, new_params_file)

    @classmethod
    def get_path_of_params(cls, id) -> Path:
        """Returns the path to the params file in the saved_params directory using the id"""
        logger.debug('Getting path of params file for id {}', id)
        from lazyft import paths

        return paths.PARAMS_DIR.joinpath(id + '.json')

    @classmethod
    def get_parameters(cls, id: str) -> dict:
        file = cls.get_path_of_params(id)
        return rapidjson.loads(file.read_text())

    @classmethod
    def remove_params_file(cls, strategy) -> None:
        """
        Remove the params file for the given strategy.
        """

        from lazyft.strategy import StrategyTools

        filepath = StrategyTools.create_strategy_params_filepath(strategy)
        logger.info('Removing strategy params: {}', filepath)
        filepath.unlink(missing_ok=True)

    @staticmethod
    def save_params_file(strategy, id: str) -> Path:
        """
        Save the current parameter dump of the strategy

        Returns: Path of the saved parameters
        """
        from lazyft.strategy import StrategyTools

        strategy_name_json = StrategyTools.create_strategy_params_filepath(strategy)
        from lazyft import paths

        strategy_file_path = paths.STRATEGY_DIR.joinpath(strategy_name_json)
        params_dir_joinpath = paths.PARAMS_DIR.joinpath(id + '.json')
        logger.debug(
            'Saving param dump {} -> {}', strategy_file_path, params_dir_joinpath
        )
        return strategy_file_path.replace(params_dir_joinpath)
