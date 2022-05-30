"""
https://kaabar-sofien.medium.com/the-catapult-indicator-innovative-trading-techniques-8910ac962c57
"""
# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from numbers import Number
from pathlib import Path
from typing import Optional, Tuple, Union

import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import pandas as pd
import pandas_ta
import talib.abstract as ta
import technical.indicators as pta
from finta import TA
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    merge_informative_pair,
)
from freqtrade.strategy.interface import IStrategy
from numpy import number
from pandas import DataFrame
from pandas_ta import ema

sys.path.append(str(Path(__file__).parent))


class Fibonacci(IStrategy):
    """
    Strategy implemented with the help of the Catapult indicator.
    """

    # region Parameters

    # endregion
    # region Params
    minimal_roi = {"0": 0.03}
    stoploss = -0.25
    # endregion
    timeframe = "5m"
    use_custom_stoploss = False

    # Recommended
    exit_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        fib = pta.fibonacci_retracements(dataframe, "high")
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "buy"] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "sell"] = 1
        return dataframe
