import dotenv
import loguru
from rich.console import Console

from . import paths

dotenv.load_dotenv()
console = Console(width=200)

logger = loguru.logger
