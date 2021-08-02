import logging

from rich.console import Console
from rich.logging import RichHandler

console = Console(width=200)

logger = logging.getLogger("lazyft")
logger.setLevel("INFO")
logger.handlers.clear()
logger.addHandler(RichHandler(rich_tracebacks=True, console=console))
