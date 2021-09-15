"""
Designed to work with the Ensemble strategy.
"""
import rapidjson

from lazyft import paths
from lazyft.models import Strategy
from lazyft.util import ParameterTools


def set_ensemble_strategies(strategies: list[Strategy]):
    """Updates the ensemble json file with the designated strategies."""
    for strategy in strategies:
        if strategy.id:
            ParameterTools.set_params_file(strategy.name, strategy.id)
        else:
            ParameterTools.remove_params_file(strategy.name)
    paths.ENSEMBLE_FILE.write_text(rapidjson.dumps([s.name for s in strategies]))


if __name__ == '__main__':
    set_ensemble_strategies(Strategy('TestStrategy'), Strategy('BinH'))
