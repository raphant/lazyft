import pathlib

BASE_DIR = pathlib.Path.cwd().resolve()
LOG_DIR = BASE_DIR.joinpath('logs')
LOG_DIR.mkdir(exist_ok=True)
CONFIG_DIR = BASE_DIR.joinpath('configs')
USER_DATA_DIR = BASE_DIR.joinpath('user_data')
STRATEGY_DIR = USER_DATA_DIR.joinpath('strategies')
HYPEROPT_RESULTS_DIR = USER_DATA_DIR.joinpath('hyperopt_results')
BACKTEST_RESULTS_DIR = USER_DATA_DIR.joinpath('backtest_results')
LAST_HYPEROPT_RESULTS_FILE = HYPEROPT_RESULTS_DIR / '.last_result.json'
LAST_BACKTEST_RESULTS_FILE = BACKTEST_RESULTS_DIR / '.last_result.json'
ENSEMBLE_FILE = STRATEGY_DIR.joinpath('ensemble.json')
HYPEROPT_LOG_PATH = LOG_DIR.joinpath('hyperopt_logs/')
HYPEROPT_LOG_PATH.mkdir(exist_ok=True)
BACKTEST_LOG_PATH = LOG_DIR.joinpath('backtest_logs/')
BACKTEST_LOG_PATH.mkdir(exist_ok=True)
PAIR_DATA_DIR = USER_DATA_DIR.joinpath('data')
CACHE_DIR = BASE_DIR.joinpath('.cache')
