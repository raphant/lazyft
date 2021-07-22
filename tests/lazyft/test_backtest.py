import pathlib

from lazyft.backtest.commands import create_commands
from lazyft.backtest.runner import BacktestRunner
from lazyft.constants import BASE_DIR
from lazyft.parameters import Parameters

STRATEGY = ['BinH-hH9Mpb']

STRATEGIES = ['BinH-6iwMJ1', 'BbandRsi-IAV7YR']
Parameters.SAVE_PATH = pathlib.Path(__file__).parent.joinpath('params.yaml')


def test_backtest_command():
    commands = create_commands(
        strategies=STRATEGY,
        config=pathlib.Path(BASE_DIR, 'config_binance2.json'),
        days=10,
        interval='5m',
    )
    runner = BacktestRunner(commands[0])
    runner.execute()
    report = runner.generate_report()
    assert any(report.winners)
    report.print_winners()
    print(report.winners_as_pairlist)
