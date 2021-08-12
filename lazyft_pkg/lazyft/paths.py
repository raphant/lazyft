import pathlib

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIRECTORY.joinpath('../../').resolve()

PARAMS_FILE = BASE_DIR.joinpath("lazy_params.json")
PARAMS_DIR = BASE_DIR.joinpath('saved_params')
LOG_DIR = BASE_DIR.joinpath('logs')
PARAMS_DIR.mkdir(exist_ok=True)
BACKTEST_RESULTS_FILE = BASE_DIR.joinpath('backtest_results.json')
CONFIG_DIR = BASE_DIR.joinpath('configs')
USER_DATA_DIR = BASE_DIR.joinpath('user_data')
STRATEGY_DIR = USER_DATA_DIR.joinpath('strategies')
ID_TO_LOAD_FILE = STRATEGY_DIR.joinpath('strategy_ids.json')
LAST_HYPEROPT_RESULTS_FILE = USER_DATA_DIR.joinpath(
    'hyperopt_results', '.last_result.json'
)
