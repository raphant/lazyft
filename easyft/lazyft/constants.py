import pathlib

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.resolve()
BASE_DIR = pathlib.Path(SCRIPT_DIRECTORY, '../../').resolve()
CONFIG_DIR = pathlib.Path(BASE_DIR, 'configs').resolve()
USER_DATA_DIR = pathlib.Path(BASE_DIR, 'user_data')
STRATEGY_DIR = pathlib.Path(USER_DATA_DIR, 'strategies')
BASE_CONFIG_PATH = pathlib.Path(BASE_DIR, 'config.json')
