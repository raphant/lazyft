import warnings
from pathlib import Path

import dotenv
import pandas as pd
from diskcache import Index

try:
    from freqtrade.configuration import Configuration
except ImportError as e:
    raise ImportError("Please install freqtrade to use LazyFT") from e

from loguru import logger
from rich import console

from . import paths, util
from .log_config import setup_logger

SETTINGS = Index(str(paths.CACHE_DIR / "settings"))

if not paths.CONFIG_DIR.exists():
    if (
        input("No configs folder found. Would you like to create want? [y/n]:").lower()
        == "y"
    ):
        paths.CONFIG_DIR.mkdir(exist_ok=False)
    else:
        raise RuntimeError(
            "No configs folder found. Please check the current working directory."
        )

if not paths.USER_DATA_DIR.exists():
    if (
        input("No user_data folder found. Would you like to create one? [y/n]:").lower()
        == "y"
    ):
        paths.USER_DATA_DIR.mkdir()
        paths.STRATEGY_DIR.mkdir()
        paths.PAIR_DATA_DIR.mkdir()
        paths.HYPEROPT_RESULTS_DIR.mkdir()
        paths.BACKTEST_RESULTS_DIR.mkdir()
    else:
        logger.warning("Continuing with no user_data folder")

dotenv.load_dotenv()

pd.set_option("display.float_format", lambda x: util.human_format(x))


setup_logger()
logger_exec = logger.bind(type="general")
tmp_dir = Path("/tmp/lazyft")

if not SETTINGS.get("CHECK_BASE_CONFIG"):
    config_files = [str(path) for path in paths.BASE_DIR.glob("config*.json")]
    if not any(config_files):
        pass
    else:
        if (
            input(
                f"Found config files in the base directory. LazyFT only uses files"
                ' in the "configs" folder. Would you like to move them to the "configs"'
                " folder? [y/n]:"
            ).lower()
            == "y"
        ):
            for path in config_files:
                Path(path).rename(paths.CONFIG_DIR / Path(path).name)
                logger.info(f"Moved {path} to {paths.CONFIG_DIR / Path(path).name}")
    SETTINGS["CHECK_BASE_CONFIG"] = True

try:
    BASIC_CONFIG = Configuration.from_files([str(paths.CONFIG_DIR / "config.json")])
except Exception as e:
    logger.warning(f"Could not load config.json: {e}")


warnings.filterwarnings(
    "ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*"
)

print = console.Console().print
