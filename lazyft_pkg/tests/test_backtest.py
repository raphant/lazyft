import pathlib

from lazyft import backtest, paths
from lazyft.backtest.commands import create_commands
from lazyft.backtest.runner import BacktestRunner
from lazyft.parameters import CommandParameters

paths.PARAMS_FILE = pathlib.Path(__file__).parent.joinpath('params.json')

STRATEGY = ['TestBinH-g1As75']
STRATEGIES = ['TestBinH-g1As75', 'TestBinH']
config_name = 'config_test.json'

days = 10


def get_commands(strategies):
    cp = CommandParameters(strategies=strategies, config=config_name, days=days)
    commands = create_commands(cp, verbose=True, skip_data_download=True)
    return commands


def test_backtest_command_no_id():
    commands = get_commands(STRATEGIES)
    runner = BacktestRunner(commands[1])
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    assert bool(runner.report)


def test_backtest_command_with_id():
    commands = get_commands(STRATEGIES)
    runner = BacktestRunner(commands[0])
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    assert bool(runner.report)


# def test_backtest_with_generated_pairlist():
#     commands = backtest.create_commands(
#         strategies=STRATEGY, interval='5m', config=config_name, days=days
#     )
#     runner = backtest.BacktestRunner(commands.pop())
#     runner.execute()
#     report = runner.generate_report()
#     report.print_winners()


def test_save_backtesting_report():
    commands = get_commands(STRATEGY)
    runner = BacktestRunner(commands[0])
    runner.execute()
    assert bool(runner.report)
    runner.report.save()


def test_multi_runner():
    commands = get_commands(STRATEGIES)
    mr = backtest.BacktestMultiRunner(commands)
    mr.execute()
    assert any(mr.reports)
    for r in mr.reports:
        assert isinstance(r, backtest.BacktestReportExporter)
