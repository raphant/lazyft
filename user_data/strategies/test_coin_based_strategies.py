from freqtrade.configuration import Configuration
from freqtrade.data.history import load_pair_history
from lazyft import paths

data_dir = paths.USER_DATA_DIR.joinpath('data', 'kucoin')


def test_populate_trend_function():
    pair = 'MATIC/USDT'
    # config = Configuration.from_files(['configs/config_3_100_unlimited_usdt.json'])
    dataframe = load_pair_history(
        datadir=data_dir,
        timeframe='5m',
        pair=pair,
        data_format="json",
    )
    dataframe = CbsPopulater.buy_trend(dataframe, pair)
