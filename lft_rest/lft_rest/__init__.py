import queue
from collections import Counter

from loguru import logger


class State:
    backtesting = False
    backtest_queue = queue.Queue()
    hyperopt_queue = queue.Queue()
    current_hyperopt = None
    current_backtests = []

    failed_hyperopts = Counter()
    failed_backtest = Counter()


class Settings:
    n_backtest_workers = 1
    max_hyperopt_attempts = 3
    max_backtest_attempts = 3
    min_avg_profit = 0.01
    max_days_since_created = 3
