import pathlib
import lazyft
import rapidjson
from lazyft.constants import BASE_DIR
from lazyft.hyperopt.runner import (
    HyperoptRunner,
    HyperoptManager,
)
from lazyft.hyperopt.report import HyperoptPerformance, HyperoptReport
from lazyft.parameters import Parameters
from lazyft.hyperopt.commands import create_commands
from lazyft.strategy import Strategy

STRATEGY = ['BinH']

STRATEGIES = ['BinH', 'BbandRsi']
Parameters.SAVE_PATH = pathlib.Path(__file__).parent.joinpath('params.yaml')


def test_get_hyperopt_runner():
    commands = create_commands(
        strategies=STRATEGY,
        config=pathlib.Path(BASE_DIR, 'config_binance.json'),
        epochs=10,
        spaces='bs',
        days=5,
    )
    runner = HyperoptRunner(commands[0])
    runner.execute()
    report = runner.generate_report()
    assert isinstance(report, HyperoptReport)
    assert report.strategy.strategy_name == STRATEGY
    assert isinstance(report.performance, HyperoptPerformance)
    assert isinstance(report.params, Parameters)


def test_param_save():
    params = {'mock': 'data'}
    strategy = Strategy.create_strategies(*STRATEGY).pop()
    hyperopt_param = Parameters(
        params, HyperoptPerformance(0, 0, 0, 0, 0, 0, 0, 0, '', 0, 0), strategy.pop()
    )
    hyperopt_param.save()
    assert Parameters.SAVE_PATH.exists()
    assert STRATEGY.pop() in rapidjson.loads(Parameters.SAVE_PATH.read_text())
    Parameters.SAVE_PATH.unlink()


def test_multiple_hyperopt_runners():
    commands = create_commands(
        strategies=STRATEGIES,
        config=pathlib.Path(lazyft.BASE_DIR, 'config_binance.json'),
        epochs=2,
        spaces='bs',
        days=10,
    )
    manager = HyperoptManager(commands)
    manager.create_runners()
    assert any(manager.runners)
    manager.execute()
    manager.generate_reports()
    assert isinstance(manager.reports, list)
    report = manager.reports[0]
    assert isinstance(report, HyperoptReport)
    best_run = manager.get_best_run()
    assert isinstance(best_run, HyperoptReport)
