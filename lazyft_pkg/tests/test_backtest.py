import pathlib

from lazyft import backtest
from lazyft.backtest.commands import create_commands
from lazyft.backtest.runner import BacktestRunner
from lazyft import paths

paths.PARAMS_FILE = pathlib.Path(__file__).parent.joinpath('params.json')

STRATEGY = ['TestBinH-g1As75']
STRATEGIES = ['TestBinH-g1As75', 'TestBinH']
config_name = 'config_test.json'

days = 10


def get_commands(strategies):
    commands = create_commands(
        strategies=strategies,
        config=config_name,
        days=days,
        interval='5m',
        verbose=True,
        skip_data_download=True,
    )
    return commands


def test_backtest_command_no_id():
    commands = get_commands(STRATEGIES)
    runner = BacktestRunner(commands[1])
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    report = runner.generate_report()
    assert any(report.winners)
    report.print_winners()
    print(report.winners_as_pairlist)


def test_backtest_command_with_id():
    commands = get_commands(STRATEGIES)
    runner = BacktestRunner(commands[0])
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    report = runner.generate_report()
    assert any(report.winners)
    report.print_winners()
    print(report.winners_as_pairlist)


# def test_backtest_with_generated_pairlist():
#     commands = backtest.create_commands(
#         strategies=STRATEGY, interval='5m', config=config_name, days=days
#     )
#     runner = backtest.BacktestRunner(commands.pop())
#     runner.execute()
#     report = runner.generate_report()
#     report.print_winners()


def test_save_backtesting_data():
    commands = backtest.create_commands(
        strategies=STRATEGY, interval='5m', config=config_name, days=days
    )
    runner = BacktestRunner(commands[0])
    runner.execute()
    report = runner.generate_report()
    id = report.save()
    assert isinstance(id, str)


def test_multi_runner():
    commands = backtest.create_commands(
        strategies=STRATEGIES, interval='5m', config=config_name, days=days
    )
    mr = backtest.BacktestMultiRunner(commands)
    mr.execute()
    mr.generate_reports()
    assert any(mr.reports)
    for r in mr.reports:
        assert isinstance(r, backtest.BacktestReport)
