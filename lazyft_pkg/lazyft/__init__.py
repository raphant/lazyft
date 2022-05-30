import warnings
from pathlib import Path

import dotenv
import pandas as pd
from freqtrade.configuration import Configuration
from rich import console

from . import paths, util
from .log_config import setup_logger

if not paths.BASE_DIR.joinpath('configs').exists():
    raise RuntimeError('No configs folder found. Please check the current working directory.')

dotenv.load_dotenv()

pd.set_option('display.float_format', lambda x: util.human_format(x))

from loguru import logger

setup_logger()
logger_exec = logger.bind(type='general')
tmp_dir = Path('/tmp/lazyft')

try:
    BASIC_CONFIG = Configuration.from_files([str(paths.CONFIG_DIR / 'config.json')])
except Exception as e:
    logger.warning(f"Could not load config.json: {e}")

warnings.filterwarnings(
    "ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*"
)

print = console.Console().print
