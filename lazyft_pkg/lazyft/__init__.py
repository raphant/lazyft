import dotenv
from rich.console import Console
from rich import traceback
from . import paths

dotenv.load_dotenv()
console = Console(width=200)
traceback.install(console=console)


import sys
from loguru import logger


def non_exec_only(record):
    return "exec" not in record["extra"]


std_sink, file_sink = logger.configure(
    handlers=[
        dict(
            sink=sys.stdout,
            level='INFO',
            backtrace=False,
            diagnose=False,
            enqueue=False,
            filter=non_exec_only,
        ),
        dict(
            sink=paths.LOG_DIR.joinpath("logs.log"),
            backtrace=True,
            diagnose=True,
            level='DEBUG',
            delay=True,
            enqueue=True,
            filter=non_exec_only,
        ),
    ]
)
