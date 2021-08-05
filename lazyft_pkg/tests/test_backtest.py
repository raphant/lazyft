from lazyft import backtest
from lazyft.backtest.commands import create_commands
from lazyft.backtest.runner import BacktestRunner

STRATEGY = ['TestBinH']
STRATEGIES = ['BinH', 'BbandRsi']
config_name = 'config_test.json'

days = 10


def test_backtest_command():
    commands = create_commands(
        strategies=STRATEGY,
        config=config_name,
        days=days,
        interval='5m',
        verbose=True,
        skip_data_download=True,
    )
    runner = BacktestRunner(commands[0])
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    report = runner.generate_report()
    assert any(report.winners)
    report.print_winners()
    print(report.winners_as_pairlist)


def test_backtest_with_generated_pairlist():
    commands = backtest.create_commands(
        strategies=STRATEGY, interval='5m', config=config_name, days=days
    )
    runner = backtest.BacktestRunner(commands.pop())
    runner.execute()
    report = runner.generate_report()
    report.print_winners()
