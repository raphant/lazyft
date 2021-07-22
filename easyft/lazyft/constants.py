import pathlib

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.resolve()
BASE_DIR = pathlib.Path(SCRIPT_DIRECTORY, '../../').resolve()
CONFIG_DIR = pathlib.Path(SCRIPT_DIRECTORY, '../../configs').resolve()
FT_DATA_DIR = pathlib.Path(BASE_DIR, 'user_data')
STUDY_DIR = pathlib.Path(FT_DATA_DIR, 'strategies', 'study')
TEMPLATE_DIR = pathlib.Path(STUDY_DIR, 'templates')
BASE_CONFIG_PATH = pathlib.Path(BASE_DIR, 'study_config.json')
