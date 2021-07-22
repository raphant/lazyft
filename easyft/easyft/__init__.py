import os
import pathlib
from loguru import logger
import sys

from rich import console

os.chdir(pathlib.Path(__file__).parent)
print = console.Console().print


logger.configure(
    handlers=[
        dict(
            sink=sys.stderr, level='INFO', backtrace=False, diagnose=False, enqueue=True
        ),
    ]
)
