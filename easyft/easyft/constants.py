import pathlib

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.resolve()
BASE_DIR = pathlib.Path(SCRIPT_DIRECTORY, '../../').resolve()
FT_DATA_DIR = pathlib.Path(BASE_DIR, 'user_data').resolve()
STUDY_DIR = pathlib.Path(FT_DATA_DIR, 'strategies', 'study').resolve()
BASE_CONFIG_PATH = pathlib.Path(BASE_DIR, 'study_config.json').resolve()
DEFAULT_SPACES = ['sell', 'buy', 'roi']
