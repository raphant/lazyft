import logging
import os
import pathlib

import dotenv
from rich.console import Console
from rich.logging import RichHandler
from . import paths

dotenv.load_dotenv()
console = Console(width=200)

logger = logging.getLogger("lazyft")
logger.setLevel('DEBUG')
logger.handlers.clear()
rh = RichHandler(rich_tracebacks=True, console=console)
rh.setLevel(os.getenv('DEBUG', "INFO"))
logger.addHandler(rh)
fh = logging.FileHandler(pathlib.Path(paths.BASE_DIR, 'logs.log'), mode='a')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
