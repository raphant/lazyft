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
import pandas_ta as pta
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


class DoubleConfirmation(IStrategy):
    """
    This strategy is based on the Double Confirmation method.
    """

    # region Parameters
    rsi_value_buy = IntParameter(1, 50, default=50, space='buy')
    rsi_period = IntParameter(7, 20, default=13, space='buy')
    rsi_value_sell = IntParameter(50, 100, default=50, space='sell')
    sar_offset = IntParameter(0, 10, default=0, space='sell')
    # conditions

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
        # sar
        # create a sar with each offset in self.sar_offset.range
        for v in self.sar_offset.range:
            psar = ta.SAR(
                dataframe['high'],
                dataframe['low'],
                offset=v,
            )
            dataframe['sar_' + str(v)] = psar
        # rsi
        # create a rsi with each period in self.rsi_period.range
        for v in self.rsi_period.range:
            dataframe['rsi_' + str(v)] = qtpylib.rsi(dataframe['close'], v)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        #     A buy (Long) signal is generated whenever the market price surpasses the Parabolic SAR
        #     while the 13-period RSI is above 50.
        conditions.append(
            (
                (
                    qtpylib.crossed_above(
                        dataframe['close'],
                        dataframe['sar_' + str(self.sar_offset.value)],
                    )
                )
                & (
                    dataframe['rsi_' + str(self.rsi_period.value)]
                    > self.rsi_value_buy.value,
                )
            )
        )
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        #     A sell (Short) signal is generated whenever the market price breaks the Parabolic SAR
        #     while the 13-period RSI is below 50.
        conditions = []
        conditions.append(
            (
                (dataframe['close'] < dataframe['sar_' + str(self.sar_offset.value)])
                & (
                    dataframe['rsi_' + str(self.rsi_period.value)]
                    < self.rsi_value_sell.value
                )
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
