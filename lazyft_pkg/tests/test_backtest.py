from lazyft.backtest.commands import create_commands
from lazyft.backtest.runner import BacktestRunner

STRATEGY = ['TestBinH']
ID = 'SdHu4J'
STRATEGIES = ['BinH', 'BbandRsi']


def test_backtest_command():
    commands = create_commands(
        strategies=STRATEGY,
        config='config_binance2.json',
        days=10,
        interval='5m',
        id=ID,
        verbose=True,
        skip_data_download=True,
    )
    runner = BacktestRunner(commands[0])
    runner.execute()
    report = runner.generate_report()
    assert any(report.winners)
    report.print_winners()
    print(report.winners_as_pairlist)
