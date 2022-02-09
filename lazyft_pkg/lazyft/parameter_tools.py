from __future__ import annotations

from pathlib import Path
from typing import Union

from loguru import logger


def get_parameters(id: str) -> dict:
    from lazyft.reports import get_hyperopt_repo

    return get_hyperopt_repo().get(id).parameters


def set_params_file(hyperopt_id: int, export_path: Path = None):
    """Load strategy parameters from a saved report."""

    from lazyft.reports import get_hyperopt_repo

    report = get_hyperopt_repo().get(hyperopt_id)
    report.export_parameters(export_path)


def remove_params_file(strategy: str, config: Union[str, Path] = None) -> None:
    """
    Remove the params file for the given strategy.
    """
    from lazyft.strategy import get_strategy_param_path
    from lazyft.config import Config

    if not config:
        config = Config('config.json')
    if isinstance(config, str):
        config = Path(config)
    filepath = get_strategy_param_path(strategy, str(config))
    logger.info('Removing strategy params: {}', filepath)
    filepath.unlink(missing_ok=True)
