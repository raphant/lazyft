import logging
import os
import sys
from functools import partial

from lazyft import paths
from lazyft.log_config import filter_log_file, non_exec_only
from lazyft.notify import notify_telegram
from loguru import logger

# logger = logging.getLogger('HBC')
# # make logger log to paths.LOG_DIR / 'backtesting_hyperopt.log' and print to stdout and set logger formatting to date, time, message
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler())
# logger.addHandler(logging.FileHandler(paths.LOG_DIR / 'backtesting_hyperopt.log'))
# logger.propagate = False
# FORMAT = "[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s] %(levelname)s: %(message)s"
# formatter = logging.Formatter(FORMAT)
# for handler in logger.handlers:
#     handler.setFormatter(formatter)
# logger_set = True


logger.add(
    paths.LOG_DIR / 'backtesting_hyperopt.log',
    rotation='1 MB',
    level='DEBUG',
    filter=lambda r: filter_log_file(r, log_type='combo'),
)
logger.add(sys.stdout, filter=lambda r: filter_log_file(r, log_type='combo'), level='INFO')

logger = logger.bind(type='combo')
notify = partial(notify_telegram, 'Auto Hyperopt & Backtest')
