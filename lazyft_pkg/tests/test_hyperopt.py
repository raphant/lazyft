import pathlib

from lazyft.hyperopt.commands import create_commands
from lazyft.hyperopt.report import HyperoptPerformance, HyperoptReport
from lazyft.hyperopt.runner import (
    HyperoptRunner,
)

STRATEGY = ['TestBinH']

STRATEGIES = ['TestBinH']
HyperoptReport.SAVE_PATH = pathlib.Path(__file__).parent.joinpath('params.json')


def test_get_hyperopt_runner():
    commands = create_commands(
        strategies=STRATEGY,
        config='config_binance.json',
        epochs=10,
        spaces='buy sell',
        days=5,
        skip_data_download=True,
        verbose=True,
    )
    runner = HyperoptRunner(commands[0])
    runner.execute()
    report = runner.generate_report()
    assert isinstance(report, HyperoptReport)
    assert report.strategy == STRATEGY.pop()
    assert isinstance(report.performance, HyperoptPerformance)
    assert isinstance(report.params, dict)

    report.save()

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
