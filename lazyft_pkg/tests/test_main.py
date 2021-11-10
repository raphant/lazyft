import pathlib

from lazyft import paths
from lazyft.config import Config
from lazyft.pairlist import load_pairlist_from_id
from lazyft.quicktools.quick_tools import QuickTools
from lazyft.reports import get_hyperopt_repo

strategy = ['BinH']
refresh_config = Config('config_binance2.json')
backtest_config_name = 'config_test.json'
backtest_config = Config(backtest_config_name)


def test_refresh_pairlist():
    whitelist = refresh_config.whitelist
    QuickTools.refresh_pairlist(refresh_config, 10, backtest_config_name)
    assert any(whitelist)


def test_download_data():
    QuickTools.download_data(refresh_config, '5m', days=5, verbose=True)


def test_pairlist_loading():
    if not any(get_hyperopt_repo()):
        return
    id = get_hyperopt_repo()[0].param_id
    pairlist = load_pairlist_from_id(id)
    assert any(pairlist)
