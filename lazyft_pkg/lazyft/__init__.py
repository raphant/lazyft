import logging
from rich.logging import RichHandler
from rich.console import Console

console = Console(width=200)

logger = logging.getLogger("lazyft")
logger.setLevel("INFO")
logger.handlers.clear()
logger.addHandler(RichHandler(rich_tracebacks=True, console=console))
