import pathlib

from lazyft import paths
from lazyft.hyperopt.commands import create_commands
from lazyft.hyperopt.report import HyperoptReportExporter
from lazyft.models import HyperoptPerformance
from lazyft.hyperopt.runner import (
    HyperoptRunner,
)
from lazyft.command_parameters import HyperoptParameters
from rich import traceback


paths.PARAMS_FILE = pathlib.Path(__file__).parent.joinpath('params.json')
paths.PARAMS_DIR = pathlib.Path(__file__).parent.joinpath('saved_params/')

STRATEGY = ['TestStrategy']
STRATEGY_WITH_ID = ['TestStrategy-test']
config_name = 'config_test.json'
epochs = 1
days = 2
min_trades = 1


def get_commands(strategy, timerange=None, spaces='roi'):
    hp = get_parameters(spaces, strategy, timerange)
    commands = create_commands(
        hp,
        verbose=True,
    )
    return commands


def get_parameters(spaces, strategy, timerange):
    hp = HyperoptParameters(
        strategies=strategy,
        config_path=config_name,
        epochs=epochs,
        spaces=spaces or 'buy sell',
        min_trades=min_trades,
        days=days,
        timerange=timerange,
    )
    return hp


def test_hyperopt():
    commands = get_commands(STRATEGY)
    runner = HyperoptRunner(commands[0], notify=False)
    runner.execute()
    report = runner.report_exporter
    assert isinstance(report, HyperoptReportExporter)
    assert report.strategy == STRATEGY[0]
    assert isinstance(report.performance, HyperoptPerformance)
    assert isinstance(report.params_file, pathlib.Path)

    print(runner.save())
    runner.report.params_file.unlink()


def test_hyperopt_with_id():
    commands = get_commands(STRATEGY_WITH_ID)
    runner = HyperoptRunner(commands[0], notify=False)
    runner.execute()
    assert bool(runner.report_exporter)


def test_build_command_with_days():
    commands = get_commands(STRATEGY)
    assert any(commands)
    print(commands[0].command_string)


# def test_celery():
#     hp = get_parameters('buy', ['BinH'], '20210801-')
#     from lazyft.background.tasks import do_hyperopt
#
#     res = do_hyperopt.delay(hp.__dict__)
#     print(res)


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
