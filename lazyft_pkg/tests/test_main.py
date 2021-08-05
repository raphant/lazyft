import pathlib

from lazyft import backtest, constants
from lazyft.config import Config
from lazyft.pairlist import Pairlist
from lazyft.quicktools.quick_tools import QuickTools

strategy = ['BinH']
refresh_config = Config('config_binance2.json')
backtest_config_name = 'config_test.json'
backtest_config = Config(backtest_config_name)
constants.PARAMS_FILE = pathlib.Path(__file__).parent.joinpath('params.json')


def test_refresh_pairlist():
    whitelist = refresh_config.whitelist
    QuickTools.refresh_pairlist(refresh_config, 10, backtest_config_name)
    assert refresh_config.whitelist != whitelist





def test_download_data():
    QuickTools.download_data(refresh_config, '5m', timerange='20210421-', verbose=True)


def test_pairlist_loading():
    pairlist = Pairlist.load_from_id('TestBinH', 'XtCr6D')
    assert isinstance(pairlist, list)
    assert pairlist == ["MATIC/USD", "ETH/USD", "BTC/USD", "USDT/USD", "SOL/USD"]
