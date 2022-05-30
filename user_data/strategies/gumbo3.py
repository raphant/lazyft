import logging
from datetime import datetime

import requests
from freqtrade.persistence import Trade
from pandas import DataFrame

from indicatormix import misc
from indicatormix.advanced_optimizer import AdvancedOptimizer
from indicatormix.strategy.advanced import IMBaseAdvancedOptimizerStrategy

# --- Do not remove these libs ---
from lft_rest.rest_strategy import BaseRestStrategy

logger = logging.getLogger(__name__)


class Gumbo3(IMBaseAdvancedOptimizerStrategy):
    # region Indicators
    buy_params_normal = [
        "sma_fast__SMA <= bb_fast__bb_upperband",
        "rsi__rsi < none",
        # 'aroon_value__aroon < none',
    ]
    sell_params_normal = [
        "ema_slow_30m__EMA <= ema_slow__EMA",
        "bb_fast_30m__bb_upperband > bb_fast__bb_lowerband",
        "ema_fast__EMA >= open",
        "supertrend_fast__supertrend < none",
        "bb_fast_1h__bb_middleband crossed_below vwap__vwap",
        "bb_slow_1h__bb_lowerband <= hema_fast_1h__hma",
    ]
    # endregion
    # region IM Config
    n_buy_conditions_per_group = 0
    n_sell_conditions_per_group = 3
    # endregion

    # region Init Adv Opt
    if __name__ in (__qualname__, f"{__qualname__}Rest"):
        ao = AdvancedOptimizer(
            misc.reverse_format_parameters(buy_params_normal, "buy"),
            misc.reverse_format_parameters(sell_params_normal, "sell"),
            should_optimize_func_kwargs=False,
            should_optimize_values=True,
            should_optimize_offsets=True,
            should_optimize_custom_stoploss=True,
        )
        use_custom_stoploss = True
        locals().update(ao.create_parameters())

    # endregion
    # region Custom Params
    buy_params = {
        "atr_1h__offset_low": 0.908,
        "bb_fast__offset_low": 0.9,
        "bb_fast__timeperiod": 20,
        "bb_slow_1h__offset_low": 0.926,
        "ema_fast__offset_low": 0.901,
        "ema_fast__timeperiod": 9,
        "ema_slow__offset_low": 0.982,
        "ema_slow__timeperiod": 100,
        "hema_fast_1h__offset_low": 0.949,
        "rsi__buy": 39,
        "rsi__timeperiod": 14,
        "sma_fast__offset_low": 0.985,
        "sma_fast__timeperiod": 9,
        "supertrend_fast__timeperiod": 5,
        "vwap__offset_low": 0.911,
        "vwap__timeperiod": 10,
        "wma_fast_1h__offset_low": 0.908,
    }
    sell_params = {
        "pHSL": -0.286,
        "pPF_1": 0.012,
        "pPF_2": 0.062,
        "pSL_1": 0.015,
        "pSL_2": 0.061,
        "atr_1h__offset_high": 0.962,
        "bb_fast__offset_high": 1.381,
        "bb_slow_1h__offset_high": 1.487,
        "ema_fast__offset_high": 0.954,
        "ema_slow__offset_high": 1.062,
        "hema_fast_1h__offset_high": 1.356,
        "rsi__sell": 70,
        "sma_fast__offset_high": 1.291,
        "vwap__offset_high": 1.362,
        "wma_fast_1h__offset_high": 1.391,
    }
    minimal_roi = {"0": 0.141, "13": 0.088, "70": 0.04, "170": 0}
    stoploss = -0.343
    timeframe = "5m"
    # endregion
    # region Recommended
    exit_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200
    # endregion


class Gumbo3Rest(BaseRestStrategy, Gumbo3):
    rest_strategy_name = "Gumbo3"
    backtest_days = 10
    hyperopt_days = 7
    min_hyperopt_trades = 3
    min_backtest_trades = 3
    hyperopt_epochs = 65
    min_avg_profit = 0.01
    request_hyperopt = False

    # def __init__(self, config: dict) -> None:
    #     Gumbo3.__init__(self, config)
    #     BaseRestStrategy.__init__(self, config)
