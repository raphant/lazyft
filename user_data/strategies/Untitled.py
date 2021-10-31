# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from numbers import Number
from pathlib import Path
from typing import Optional, Union, Tuple

import freqtrade.vendor.qtpylib.indicators as qtpylib
import pandas as pd
import talib.abstract as ta
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

sys.path.append(str(Path(__file__).parent))

import custom_indicators as cta

# --------------------------------


class Untitled(IStrategy):
    """https://12ft.io/proxy?q=https%3A%2F%2Fmedium.com%2Fgeekculture%2Fdetecting-statistical-overbought-oversold-levels-on-technical-indicators-f8707740cb82"""

    # CategoricalParameter(['type1', 'type2'])

    # region Params
    minimal_roi = {"0": 0.03}
    stoploss = -0.25
    # endregion

    timeframe = '5m'
    use_custom_stoploss = False

    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 500

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        def buy_signal(series: pd.Series) -> bool:
            # RSI reaches its lower barrier with the two previous readings above the lower barrier
            two_back, one_back, current = series.items()
            current_lowerband = dataframe.iloc[current[0]]["rsi_lowerband"]
            one_back_lowerband = dataframe.iloc[one_back[0]]["rsi_lowerband"]
            two_back_lowerband = dataframe.iloc[two_back[0]]["rsi_lowerband"]
            return (
                two_back[1] > two_back_lowerband
                and one_back[1] > one_back_lowerband
                and current[1] < current_lowerband
            )

        def sell_signal(series) -> bool:
            # RSI reaches its upper barrier with the two previous readings below the upper barrier
            two_back, one_back, current = series.items()
            current_upperband = dataframe.iloc[current[0]]["rsi_upperband"]
            one_back_upperband = dataframe.iloc[one_back[0]]["rsi_upperband"]
            two_back_upperband = dataframe.iloc[two_back[0]]["rsi_upperband"]
            return (
                two_back[1] < two_back_upperband
                and one_back[1] < one_back_upperband
                and current[1] > current_upperband
            )

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=20)
        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(dataframe['rsi'], window=500, stds=2)

        dataframe['rsi_lowerband'] = bollinger['lower']
        dataframe['rsi_middleband'] = bollinger['mid']  # rsi moving average
        dataframe['rsi_upperband'] = bollinger['upper']
        dataframe['long'] = (
            dataframe['rsi'].rolling(3).apply(buy_signal, raw=False).fillna(0)
        )
        dataframe['short'] = (
            dataframe['rsi'].rolling(3).apply(sell_signal, raw=False).fillna(0)
        )
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # conditions = []
        #
        # conditions.append((dataframe['rsi'] <= dataframe['rsi_lowerband']))
        # conditions.append(dataframe['volume'].gt(0))
        #
        # if conditions:
        #     dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        dataframe.loc[(dataframe['long'] == 1), 'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['short'] == 1), 'sell'] = 1
        dataframe['sell'] = 0
        return dataframe
