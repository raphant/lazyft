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

import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import pandas as pd
import pandas_ta
import talib.abstract as ta
from finta import TA
from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IntParameter,
    DecimalParameter,
    merge_informative_pair,
    CategoricalParameter,
)
from freqtrade.strategy.interface import IStrategy
from numpy import number
from pandas import DataFrame
from pandas_ta import ema
import logging

sys.path.append(str(Path(__file__).parent))
import custom_indicators as ci

logger = logging.getLogger(__name__)


class Gumbo2(IStrategy):
    # region Parameters
    stoch_low = IntParameter(0, 50, default=20, space="buy", optimize=True)
    t3_periods = IntParameter(5, 20, default=5, space="buy", optimize=True)
    stock_periods = IntParameter(50, 90, default=80, space="buy", optimize=True)
    stoch_high = IntParameter(60, 100, default=80, space="sell", optimize=True)

    # endregion
    # region Params
    minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
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

    def informative_pairs(self) -> ListPairsWithTimeframes:
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, '1h') for pair in pairs]
        return informative_pairs

    def populate_informative_indicators(self, dataframe: DataFrame, metadata):
        informative = self.dp.get_pair_dataframe(
            pair=metadata['pair'], timeframe=self.inf_timeframe
        )
        # t3 from custom_indicators
        informative['T3'] = ci.T3(informative)
        # sar
        informative['SAR'] = ta.SAR(informative['high'], informative['low'])
        # bollinger bands 40
        bbands = ta.BBANDS(dataframe, timeperiod=40)
        dataframe['bb_middleband_40'] = bbands['middleband']
        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, self.inf_timeframe
        )

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ema 100
        dataframe['EMA_100'] = ta.EMA(dataframe, timeperiod=100)
        # wma 100
        dataframe['WMA_100'] = ta.WMA(dataframe, timeperiod=100)
        # wma
        dataframe['WMA'] = ta.WMA(dataframe)
        # sar
        dataframe['SAR'] = ta.SAR(dataframe['high'], dataframe['low'])
        # stochastic
        # stochastic windows
        # t3
        for i in self.t3_periods.range:
            dataframe[f'T3_{i}'] = ci.T3(dataframe, i)
        for i in self.stock_periods.range:
            dataframe[f'stoch_{i}'] = ci.stoch_sma(dataframe, window=i)
        dataframe = self.populate_informative_indicators(dataframe, metadata)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # sar > close
        conditions.append(dataframe['SAR'] > dataframe['close'])
        # wma < sar_1h
        conditions.append(dataframe['WMA'] < dataframe['SAR_1h'])
        # stoch <= stock value
        conditions.append(
            dataframe[f'stoch_{self.stock_periods.value}'] <= self.stoch_low.value
        )
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # stoch > 80
        conditions.append(
            dataframe[f'stoch_{self.stock_periods.value}'] > self.stoch_high.value
        )
        # t3 >= middleband_40
        conditions.append(
            dataframe[f'T3_{self.t3_periods.value}'] >= dataframe['bb_middleband_40']
        )
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
        return dataframe
