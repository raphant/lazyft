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

sys.path.append(str(Path(__file__).parent))


class CatapultV2(IStrategy):
    """
    Strategy implemented with the help of the Catapult indicator.
    """

    # region Parameters
    rvi_buy = IntParameter(10, 50, default=50, space='buy')
    rvi_rolling_buy = IntParameter(4, 10, default=6, space='buy')
    rsi_buy = IntParameter(30, 70, default=70, space='buy')
    rvi_sell = IntParameter(50, 100, default=50, space='sell')
    rsi_sell = IntParameter(50, 100, default=50, space='sell')

    # conditions
    enable_sell_rvi = CategoricalParameter([True, False], default=True, space='sell')
    flip_sell_rvi = CategoricalParameter([True, False], default=False, space='sell')
    enable_sell_rvi_rolling = CategoricalParameter(
        [True, False], default=False, space='sell'
    )

    # endregion
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
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # The Base - Volatility
        # The 21-period Relative Volatility Index will give the first trigger by stating that as of now,
        # there will be above average volatility and therefore, possible a directional move.
        dataframe['rvi'] = relative_volatility_index(dataframe, 21)
        # The Arm - Momentum
        # The 14-period Relative Strength Index will give the likelihood direction of the move by saying that
        # if the reading is above 50, then the move is likely bullish while if the reading is below 50,
        # then the move is likely bearish.
        dataframe['rsi'] = pandas_ta.rsi(dataframe['close'], length=14)
        # The Frame - Directional Filter
        # The 200-period simple moving average will add conviction to the likelihood direction of the move.
        # If the market is above the 200-period moving average then we understand that there is bullish pressure
        # and quite likely a continuation to the upside.
        # Similarly, if the market is below the 200-period moving average then we understand that there is bearish
        # pressure and quite likely a continuation to the downside.
        dataframe['sma200'] = pandas_ta.sma(dataframe['close'], length=200)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        def rvi_condition_bull(series):
            return series.iloc[-1] < self.rvi_buy.value and all(
                s > self.rvi_buy.value for s in series[:-1:]
            )

        rolling_rvi_bull = (
            dataframe['rvi']
            .rolling(self.rvi_rolling_buy.value)
            .apply(rvi_condition_bull)
            .fillna(0.0)
        )
        conditions = []
        conditions.append(
            (
                (rolling_rvi_bull == 1)
                & (dataframe['rsi'] > self.rsi_buy.value)
                & (dataframe['close'] > dataframe['sma200'])
            )
        )
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        def rvi_condition_bear(series):
            return series.iloc[-1] > self.rvi_sell.value and all(
                s < self.rvi_sell.value for s in series[:-1:]
            )

        conditions = []
        if self.enable_sell_rvi_rolling.value:
            rolling_rvi_bear = (
                dataframe['rvi']
                .rolling(self.rvi_rolling_buy.value)
                .apply(rvi_condition_bear)
                .fillna(0.0)
            )
            conditions.append((rolling_rvi_bear == 1))

        if self.enable_sell_rvi.value:
            if self.flip_sell_rvi.value:
                cond = dataframe['rvi'] > self.rvi_sell.value
            else:
                cond = dataframe['rvi'] < self.rvi_sell.value
            conditions.append(cond)
        conditions.append(
            (
                (dataframe['rsi'] > self.rsi_sell.value)
                & (dataframe['close'] < dataframe['sma200'])
            )
        )
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe


def relative_volatility_index(
    dataframe: DataFrame, periods: int = 14, ema_length=14
) -> DataFrame:
    # calculate std

    df = dataframe.copy()
    df['std'] = qtpylib.rolling_std(df['close'], periods, min_periods=periods)
    df['close_delta'] = dataframe['close'] - dataframe['close'].shift(1)
    df['upper'] = 0.0
    df.loc[df.close_delta > 0, 'upper'] = df['std']
    df['lower'] = 0.0
    df.loc[df.close_delta < 0, 'lower'] = df['std']
    df['upper_ema'] = ema(df['upper'].fillna(0.0), length=ema_length)
    df['lower_ema'] = ema(df['lower'].fillna(0.0), length=ema_length)
    df['rvi'] = df['upper_ema'] / (df['upper_ema'] + df['lower_ema']) * 100
    return df['rvi']
