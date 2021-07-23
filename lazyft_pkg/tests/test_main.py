from lazyft import backtest
from lazyft.quicktools.config import Config
from lazyft.quicktools.quick_tools import QuickTools

strategy = ['BinH']
refresh_config = Config('config_binance2.json')
backtest_config_name = 'config_test.json'
backtest_config = Config(backtest_config_name)


def test_refresh_pairlist():
    whitelist = refresh_config['exchange']['pair_whitelist']
    QuickTools.refresh_pairlist(refresh_config, 50, backtest_config_name)
    assert refresh_config['exchange']['pair_whitelist'] != whitelist


def test_backtest_with_generated_pairlist():
    commands = backtest.create_commands(
        strategies=strategy, interval='5m', config=backtest_config.path, days=100
    )
    runner = backtest.BacktestRunner(commands.pop())
    runner.execute()
    report = runner.generate_report()
    report.print_winners()


def test_download_data():
    QuickTools.download_data(refresh_config, '5m', timerange='20210421-', verbose=True)
