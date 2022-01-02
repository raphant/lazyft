from pathlib import Path

from freqtrade.data.history import load_pair_history
from freqtrade.strategy import IStrategy

from cbs import CbsConfiguration, Strategy
from cbs.mapper import Mapper
from cbs.populator import Populator
from lazyft import paths

data_dir = paths.USER_DATA_DIR.joinpath('data', 'binanceus')
STRATEGY = 'DefaultStrategy'
cbs_config = CbsConfiguration(map_file=Path('.').joinpath('test_map.json'))
ft_config = {}
ft_config.update(
    {
        'user_data_dir': paths.USER_DATA_DIR,
        'strategy_path': paths.STRATEGY_DIR,
    },
)

strategy_dict = {'strategy_name': STRATEGY, 'params': {'test': True}}
strategy_obj = Strategy(**strategy_dict, pair='MATIC/USD')


def patch_mapper(mocker, return_value=None):
    mocker.patch(
        'cbs.mapper.Mapper.load',
        return_value=return_value or {'MATIC/USD': [strategy_dict]},
    )


def test_load_strategy():
    strategy = Populator.load_strategy(strategy_obj, parent_strategy=ft_config)
    assert isinstance(strategy, IStrategy)
    assert strategy_obj.tmp_path.exists()
    assert (strategy_obj.tmp_path / strategy_obj.strategy_file_name).exists()


def test_mapper(mocker):
    patch_mapper(mocker)

    mapper = Mapper(cbs_config)
    # make sure TestStrategy is not in MATIC/USD

    strategies = mapper.get_strategies('MATIC/USD')
    print(strategies)
    assert any(strategies)
    assert 'TestStrategy' not in strategies


def test_map_not_found(mocker):
    patch_mapper(mocker)

    mapper = Mapper(cbs_config)
    assert mapper.get_strategies('MATIC/USDT') == []


def test_populate_trend_function(mocker):
    patch_mapper(mocker)

    pair = 'MATIC/USD'
    # config = Configuration.from_files(['configs/config_3_100_unlimited_usdt.json'])
    dataframe = load_pair_history(
        datadir=data_dir,
        timeframe='5m',
        pair=pair,
        data_format="json",
    )
    mapper = Mapper(cbs_config)
    ft_config['strategy'] = STRATEGY
    dataframe = Populator.populate_indicators(ft_config, dataframe, pair, mapper)
    dataframe = Populator.buy_trend(ft_config, dataframe, pair, mapper)
    dataframe = Populator.sell_trend(ft_config, dataframe, pair, mapper)
    assert dataframe.iloc[0]['buy'] == 1
    assert dataframe.iloc[0]['sell'] == 0
    assert 'test' in dataframe


def test_coin_strategy_config(mocker):
    patch_mapper(mocker, return_value={})

    mapper = Mapper(cbs_config)
    current_mapping = mapper.get_maps()
    assert isinstance(current_mapping, dict)
    mapper.map(pair='MATIC/USD', strategy_name=STRATEGY)
    test_map = mapper.get_strategies(pair='MATIC/USD')
    assert test_map == [strategy_obj]


def test_cache_strategy(mocker):
    patch_mapper(mocker)
    strategy = Populator.load_strategy(strategy_obj, parent_strategy=ft_config)
    print(strategy)
    assert strategy_obj.joined_name in Populator.cached_strategies
