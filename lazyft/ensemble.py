"""
Designed to work with the Ensemble strategy.
"""
from __future__ import annotations
import rapidjson

from lazyft import paths, parameter_tools
from lazyft.strategy import Strategy


def set_ensemble_strategies(strategies: list[Strategy]):
    """Updates the ensemble json file with the designated strategies."""
    if not strategies:
        return []
    for strategy in strategies:
        if strategy.id:
            parameter_tools.set_params_file(strategy.id)
        else:
            parameter_tools.remove_params_file(strategy.name)

    paths.ENSEMBLE_FILE.write_text(rapidjson.dumps([s.name for s in strategies]))
    return strategies


if __name__ == '__main__':
    set_ensemble_strategies([Strategy('TestStrategy'), Strategy('BinH')])
