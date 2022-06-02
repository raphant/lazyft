from lazyft.config import Config
from lazyft.pairlist import load_pairlist_from_id, refresh_pairlist
from lazyft.reports import get_hyperopt_repo

strategy = ["BinH"]
refresh_config = Config("config_binance2.json")
backtest_config_name = "config_test.json"
backtest_config = Config(backtest_config_name)


def test_refresh_pairlist():
    whitelist = refresh_config.whitelist
    refresh_pairlist(refresh_config, 10, backtest_config_name)
    assert any(whitelist)


def test_download_data():
    NotImplementedError("TODO")


def test_pairlist_loading():
    if not any(get_hyperopt_repo()):
        return
    id = get_hyperopt_repo()[0].param_id
    pairlist = load_pairlist_from_id(id)
    assert any(pairlist)
