import pathlib

from lazyft import paths
from lazyft.hyperopt.commands import create_commands
from lazyft.hyperopt.report import HyperoptPerformance, HyperoptReport
from lazyft.hyperopt.runner import (
    HyperoptRunner,
)
from lazyft.parameters import HyperoptParameters

paths.PARAMS_FILE = pathlib.Path(__file__).parent.joinpath('params.json')

STRATEGY = ['TestBinH']
STRATEGY_WITH_ID = ['TestBinH-fcOsWD']
config_name = 'config_test.json'
epochs = 60
days = 5
min_trades = 1


def get_commands(strategy, timerange=None, spaces=None):
    hp = HyperoptParameters(
        strategies=strategy,
        config=config_name,
        epochs=epochs,
        spaces=spaces or 'buy sell',
        min_trades=min_trades,
        days=days,
        timerange=timerange,
    )
    commands = create_commands(
        hp,
        skip_data_download=True,
        verbose=True,
    )
    return commands


def test_hyperopt():
    commands = get_commands(STRATEGY)
    runner = HyperoptRunner(commands[0])
    runner.execute()
    report = runner.report
    assert isinstance(report, HyperoptReport)
    assert report.strategy == STRATEGY[0]
    assert isinstance(report.performance, HyperoptPerformance)
    assert isinstance(report.params_file, pathlib.Path)

    print(report.save())


def test_hyperopt_with_id():
    commands = get_commands(STRATEGY_WITH_ID)
    runner = HyperoptRunner(commands[0])
    runner.execute()
    assert bool(runner.report)


def test_build_command():
    commands = get_commands(STRATEGY, timerange='20210601-')
    assert len(commands) == len(STRATEGY)
    print(commands[0].build_command())


def test_build_command_with_days():
    commands = get_commands(STRATEGY)
    assert any(commands)
    print(commands[0].command_string)


# def test_param_save():
#     params = {'mock': 'data'}
#     ...


# def test_multiple_hyperopt_runners():
#     commands = create_commands(
#         strategies=STRATEGIES,
#         config=pathlib.Path(lazyft.constants.CONFIG_DIR, 'config_binance.json'),
#         epochs=2,
#         spaces='bs',
#         days=10,
#     )
#     manager = HyperoptManager(commands)
#     manager.create_runners()
#     assert any(manager.runners)
#     manager.execute()
#     manager.generate_reports()
#     assert isinstance(manager.reports, list)
#     report = manager.reports[0]
#     assert isinstance(report, HyperoptReport)
#     best_run = manager.get_best_run()
#     assert isinstance(best_run, HyperoptReport)
