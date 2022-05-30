from lazyft.combo_optimization.combo_optimizer import ComboOptimizer
from lazyft.command_parameters import BacktestParameters, HyperoptParameters
from lazyft.config import Config

days = 365
starting_balance = 100
max_open_trades = 4
stake_amount = 25
interval = '15m'
use_custom_stoploss = False
binance = Config('binance_refresh_december.json')
bin_us = Config("config.binanceus.json")

h_params = HyperoptParameters(
    epochs=50,
    config_path=binance,
    days=days,
    spaces="buy sell",
    # loss='ROIAndProfitHyperOptLoss',
    loss='CalmarHyperOptLoss',
    interval=interval,
    min_trades=100,
    starting_balance=starting_balance,
    max_open_trades=max_open_trades,
    stake_amount=stake_amount,
    jobs=-2,
    download_data=True,
    custom_spaces='',
    custom_settings={'use_custom_stoploss': use_custom_stoploss, 'timeframe': interval},
    tag='auto',
)

b_params = BacktestParameters(
    # timerange="20200101-",
    config_path=bin_us,
    days=days,
    stake_amount=stake_amount,
    starting_balance=starting_balance,
    max_open_trades=max_open_trades,
    timeframe_detail='5m',
    download_data=True,
    tag="",
    custom_settings={'use_custom_stoploss': use_custom_stoploss, 'timeframe': interval},
)
"""
if is_hyperopt:
    maximum_drawdown = 0.4
    minimum_profit_pct = 1
    minimum_win_rate = 0.4
    minimum_ppt = 0.007
    # logger.info(f'Reqs: Drawdown: {drawdown}, Profit Pct: {profit_pct}, Win rate: {win_rate}, Profit per trade: {ppt}')
else:
    maximum_drawdown = 0.4
    minimum_profit_pct = 0.4
    minimum_win_rate = 0.4
    minimum_ppt = 0.009
    """
hyperopt_requirements = {
    'maximum_drawdown': 0.4,
    'minimum_profit_pct': 1,
    'minimum_win_rate': 0.4,
    'minimum_ppt': 0.007,
}
backtest_requirements = {
    'maximum_drawdown': 0.4,
    'minimum_profit_pct': 0.4,
    'minimum_win_rate': 0.4,
    'minimum_ppt': 0.009,
}


def test_combo_opt():
    optimizer = ComboOptimizer(backtest_requirements, hyperopt_requirements, 1)
    optimizer.prepare('BatsContest', h_params, False)
    optimizer.start_optimization()
