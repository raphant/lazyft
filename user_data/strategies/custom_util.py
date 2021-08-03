# noinspection PyMethodParameters
import pathlib

import rapidjson

script_directory = pathlib.Path(__file__).parent
id_file = script_directory.joinpath('strategy_ids.json').resolve()
params_file = pathlib.Path(script_directory, '../', '../', 'lazy_params.json').resolve()


def load(strategy_name: str):

    # print(params_file, params_file.exists())
    if not (params_file.exists() and id_file.exists()):
        print('DEBUG: Params file or ID file does not exist')
        return {}
    try:
        id = rapidjson.loads(id_file.read_text())[strategy_name]
    except KeyError:
        print('DEBUG: Id not found for', strategy_name)
        print('DEBUG: ID path:', str(id_file))
        return {}
    params = rapidjson.loads(params_file.read_text())
    if strategy_name not in params:
        print('WARNING: No params found for', strategy_name)
        return {}
    params = params[strategy_name][id]['params']
    print(f'DEBUG: Loaded params from id: "{id}"')
    print(f'DEBUG: Loaded params: "{params}"')
    return params
