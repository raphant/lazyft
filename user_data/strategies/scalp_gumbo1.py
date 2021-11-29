"""
https://kaabar-sofien.medium.com/the-catapult-indicator-innovative-trading-techniques-8910ac962c57
"""
# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from numbers import Number
from pathlib import Path
from pprint import pprint
from typing import Optional, Union, Tuple

import freqtrade.vendor.qtpylib.indicators as qta
import numpy as np
import pandas as pd
import pandas_ta
import talib.abstract as ta
import custom_indicators as cta
from finta import TA
from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IntParameter,
    DecimalParameter,
    merge_informative_pair,
    CategoricalParameter,
    informative,
)
from freqtrade.strategy.interface import IStrategy
from numpy import number
from pandas import DataFrame
from pandas_ta import ema
import logging

sys.path.append(str(Path(__file__).parent))
import custom_indicators as ci

logger = logging.getLogger(__name__)


class ScalpGumbo1(IStrategy):
    # region Parameters
    t3_periods = IntParameter(5, 20, default=5, space="buy", optimize=True)
    sell_rsi_value = IntParameter(50, 100, default=70, space="sell", optimize=True)
    # endregion
    # region Params
    minimal_roi = {"0": 0.204, "26": 0.069, "84": 0.038, "120": 0}

    stoploss = -0.25
    # endregion
    timeframe = '5m'
    use_custom_stoploss = False
    inf_timeframe = '1h'
    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    def __init__(self, config: dict):
        super().__init__(config)

    @informative('30m')
    def populate_indicators_30m(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:
        ohlc = cta.heiken_ashi(dataframe)
        dataframe['hma_fast'] = qta.hull_moving_average(ohlc['close'], window=9)
        dataframe['hma_slow'] = qta.hull_moving_average(ohlc['close'], window=200)
        return dataframe

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # bollinger bands 50
        ohlc = cta.heiken_ashi(dataframe)

        bbands = ta.BBANDS(ohlc, timeperiod=50)
        dataframe['bb_lowerband_slow'] = bbands['lowerband']
        # dataframe['bb_middleband_slow'] = bbands['middleband']
        # dataframe['bb_upperband_slow'] = bbands['upperband']
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ohlc = cta.heiken_ashi(dataframe)
        dataframe['rsi'] = ta.RSI(ohlc)
        # t3
        for i in self.t3_periods.range:
            dataframe[f'T3_{i}'] = ci.T3(ohlc, i)

        # Scalp
        dataframe['atr'] = ta.ATR(
            ohlc['high'], ohlc['low'], ohlc['close'], timeperiod=5
        )
        dataframe['atr_ts1'] = ohlc['close'] - (3 * dataframe['atr'])
        dataframe['atr_ts2'] = dataframe['atr_ts1'].cummax()
        dataframe = dataframe.join(cta.supertrend(ohlc, multiplier=3, period=5))
        dataframe['color'] = cta.chop_zone(ohlc, 30)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append((dataframe['supertrend_crossed_up']))
        conditions.append(dataframe['close'] > dataframe['atr_ts1'])
        conditions.append(
            dataframe['color'].str.contains('turquoise|dark_green|pale_green')
        )
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # 1h bb crossed_above t3
        conditions.append(
            (
                qta.crossed_above(
                    dataframe['bb_lowerband_slow_1h'],
                    dataframe[f'T3_{self.t3_periods.value}'],
                )
            )
        )
        # rsi <= sell_rsi_value
        # hma fast 30m crossed_below hma slow 30m
        conditions.append(
            qta.crossed_below(dataframe['hma_fast_30m'], dataframe['hma_slow_30m'])
            & (dataframe['rsi'] <= self.sell_rsi_value.value)
        )
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
        return dataframe
