"""
https://kaabar-sofien.medium.com/the-catapult-indicator-innovative-trading-techniques-8910ac962c57
"""
# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from numbers import Number
from pathlib import Path
from typing import Optional, Union, Tuple

import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import pandas as pd
import pandas_ta
import talib.abstract as ta
from finta import TA
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
from indicator_opt import IndicatorOptHelper, indicators

sys.path.append(str(Path(__file__).parent))


logger = logging.getLogger(__name__)


class IndicatorMix(IStrategy):
    """
    Strategy implemented with the help of the Catapult indicator.
    """

    # region Parameters
    buy_comparison = IntParameter(0, 1, default=0, space='buy')
    sell_comparison = IntParameter(0, 1, default=0, space='sell')

    # endregion
    # region Params
    minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
    stoploss = -0.25
    # endregion
    timeframe = '5m'
    use_custom_stoploss = False

    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.iopt = IndicatorOptHelper.get()
        # region Parameters
        self.buy_comparison = self.iopt.get_parameter('buy', default=4)
        self.sell_comparison = self.iopt.get_parameter('sell')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for i, v in indicators.items():
            dataframe = v.populate(dataframe)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        combo = self.iopt.combinations[self.buy_comparison.value]
        conditions = []
        for c in combo.comparisons:
            conditions.append(self.iopt.compare(dataframe, c, 'buy'))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        combo = self.iopt.combinations[self.sell_comparison.value]
        conditions = []

        for c in combo.comparisons:
            conditions.append(self.iopt.compare(dataframe, c, 'sell'))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe
