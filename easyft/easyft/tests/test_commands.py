import json
import pathlib
from pprint import pprint

import pytest
from easyft import SingleCoinBacktest, SingleCoinStrategy, Hyperopt, StudyManager, Result

handler = StudyManager(strategies=['BinH'])


@pytest.fixture(scope='module')
def result():
    study = handler.new_hyperopt('MATIC/USD', intervals=1, epochs=30, min_trades=1)
    assert isinstance(study, Hyperopt)
    assert pathlib.Path(study.config_path).exists()
    config = json.loads(study.config_path.read_text())
    assert 'MATIC/USD' in config['exchange']['pair_whitelist']

    study.start()
    study.join()
    assert any(study.results)
    for r in study.results:
        pprint(r)
    return study.results.pop()


def test_backtest(result: Result):
    strategy = SingleCoinStrategy('BinH')
    strategy.create_strategy_with_param_id('MATIC/USD', result.id)
    backtest = SingleCoinBacktest(strategy, 'MATIC/USD', result.id, days=30)
    backtest.start()
    backtest.join()
    backtest.log(backtest.results)
