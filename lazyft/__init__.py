import warnings
from pathlib import Path

import dotenv
import pandas as pd
from diskcache import Index
from freqtrade.configuration.directory_operations import create_userdata_dir

try:
    from freqtrade.configuration import Configuration
except ImportError as e:
    raise ImportError("Please install freqtrade to use LazyFT") from e

from loguru import logger
from rich import console

from . import paths, util
from .log_config import setup_logger
from .lft_settings import LftSettings

dotenv.load_dotenv()
pd.set_option("display.float_format", lambda x: util.human_format(x))
setup_logger()
logger_exec = logger.bind(type="general")
tmp_dir = Path("/tmp/lazyft")
warnings.filterwarnings(
    "ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*"
)

# noinspection PyShadowingBuiltins
print = console.Console().print

if not paths.CONFIG_DIR.exists():
    if input("No configs folder found. Would you like to create one? [y/n]:").lower() == "y":
        paths.CONFIG_DIR.mkdir(exist_ok=False)
    else:
        raise RuntimeError("No configs folder found. Please check the current working directory.")

    config_files = [str(path) for path in paths.BASE_DIR.glob("config*.json")]
    if not any(config_files):
        logger.warning(
            "No config files found. Please copy existing config files to the configs "
            "folder or create a new one using `freqtrade new-config`."
        )
    else:
        if (
            input(
                "Found config files in the base directory. LazyFT only uses files"
                ' in the "configs" folder. Would you like me to move them to the "configs"'
                " folder? [y/n]:"
            ).lower()
            == "y"
        ):
            for path in config_files:
                Path(path).rename(paths.CONFIG_DIR / Path(path).name)
                logger.info(f"Moved {path} to {paths.CONFIG_DIR / Path(path).name}")

if not paths.USER_DATA_DIR.exists():
    if input("No user_data folder found. Would you like me to create one? [y/n]:").lower() == "y":
        create_userdata_dir(paths.USER_DATA_DIR, create_dir=True)
    else:
        logger.warning("Continuing with no user_data folder")

settings = LftSettings.load()

if not settings.base_config_path:
    settings.base_config_path = Path(
        input("Please enter the path to your base config file [configs/config.json]: ") or str(
            paths.CONFIG_DIR / "config.json"))

    if not settings.base_config_path.exists():
        raise RuntimeError("Invalid path to base config file")
    settings.save()

BASIC_CONFIG = Configuration.from_files([str(settings.base_config_path)])
