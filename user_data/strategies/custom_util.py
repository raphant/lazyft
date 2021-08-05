# noinspection PyMethodParameters
import logging
import pathlib

import rapidjson

logger = logging.getLogger(__name__)

script_directory = pathlib.Path(__file__).parent
id_file = script_directory.joinpath('strategy_ids.json').resolve()
params_file = pathlib.Path(script_directory, '../', '../', 'lazy_params.json').resolve()


def load(strategy_name: str):

    # print(params_file, params_file.exists())
    if not (params_file.exists() and id_file.exists()):
        logger.error(
            'Params file or ID file does not exist \n %s | %s', id_file, params_file
        )
        return {}
    try:
        id = rapidjson.loads(id_file.read_text())[strategy_name]
    except KeyError:
        logger.info('Id not found for %s', strategy_name)
        logger.info('ID path: %s', str(id_file))
        return {}
    params = rapidjson.loads(params_file.read_text())
    if strategy_name not in params:
        logger.warning('No params found for %s', strategy_name)
        return {}
    params = params[strategy_name][id]['params']
    logger.info('Loaded params from id %s', {id})
    logger.info('Loaded params: %s', params)
    return params
