import pathlib

from lazyft.config import Config
from lazyft.hyperopt.commands import create_commands
from lazyft.hyperopt.report import HyperoptPerformance, HyperoptReport
from lazyft.hyperopt.runner import (
    HyperoptRunner,
)

STRATEGY = ['TestBinH']

HyperoptReport.SAVE_PATH = pathlib.Path(__file__).parent.joinpath('params.json')
config_name = 'config_test.json'
epochs = 60
days = 5
min_trades = 1


def test_hyperopt():
    commands = create_commands(
        strategies=STRATEGY,
        config=config_name,
        epochs=epochs,
        spaces='buy sell',
        days=days,
        min_trades=min_trades,
        skip_data_download=True,
        verbose=True,
    )
    runner = HyperoptRunner(commands[0])
    runner.execute()
    report = runner.report
    assert isinstance(report, HyperoptReport)
    assert report.strategy == STRATEGY[0]
    assert isinstance(report.performance, HyperoptPerformance)
    assert isinstance(report.params, dict)

    print(report.save())


def test_build_command():
    config = Config(config_name)
    commands = create_commands(
        strategies=STRATEGY,
        config=str(config),
        epochs=epochs,
        min_trades=min_trades,
        spaces='buy sell',
        timerange='20210601-',
        skip_data_download=True,
        verbose=True,
        pairs=config.whitelist,
    )
    assert len(commands) == len(STRATEGY)
    print(commands[0].build_command())


def test_build_command_with_days():
    config = Config(config_name)
    commands = create_commands(
        strategies=STRATEGY,
        config=str(config),
        epochs=epochs,
        spaces='buy sell',
        days=days,
        min_trades=min_trades,
        skip_data_download=False,
        verbose=True,
        pairs=config.whitelist,
    )
    assert any(commands)
    print(commands[0].build_command())


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
