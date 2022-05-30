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
import pandas_ta as pta
import talib.abstract as ta
from finta import TA
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    informative,
    merge_informative_pair,
)
from freqtrade.strategy.interface import IStrategy
from numpy import number
from pandas import DataFrame
from pandas_ta import ema

sys.path.append(str(Path(__file__).parent))


class PairTrading(IStrategy):
    """
    Strategy implemented with the help of the Catapult indicator.
    """

    # region Parameters
    buy_diff = DecimalParameter(low=-0.02, high=-0.005, default=0.01, space="buy")
    sell_diff = DecimalParameter(low=-0.001, high=0, default=0, space="sell")

    # conditions
    # endregion
    # region Params
    minimal_roi = {"0": 0.03}
    stoploss = -0.25
    # endregion
    timeframe = "30m"
    use_custom_stoploss = False

    # Recommended
    exit_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    @informative("30m", "BTC/{stake}")
    def populate_indicators_btc_1h(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:
        ohlc4 = pta.ohlc4(
            dataframe["open"], dataframe["high"], dataframe["low"], dataframe["close"]
        )
        dataframe["btc_roc"] = ohlc4.pct_change()
        # dataframe['btc_change'] = dataframe['close'].pct_change()
        return dataframe

    # def informative_pairs(self):
    #     return [('BTC/USDT', '30m')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ohlc4 = pta.ohlc4(
            dataframe["open"], dataframe["high"], dataframe["low"], dataframe["close"]
        )
        dataframe["roc"] = ohlc4.pct_change()
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["diff"] = dataframe["btc_usdt_btc_roc_30m"] - dataframe["roc"]
        conditions = [(dataframe["diff"] <= self.buy_diff.value)]
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "buy"] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # sell when diff is zero
        conditions.append(dataframe["diff"] >= self.sell_diff.value)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "sell"] = 1
        return dataframe


def relative_volatility_index(
    dataframe: DataFrame, period: int = 14, ema_length=14
) -> DataFrame:
    # calculate std
    df = dataframe.copy()
    df["std"] = df["close"].rolling(period).std()
    df["close_delta"] = dataframe["close"] - dataframe["close"].shift(1)
    df["upper"] = 0.0
    df.loc[df.close_delta > 0, "upper"] = df["std"]
    df["lower"] = 0.0
    df.loc[df.close_delta < 0, "lower"] = df["std"]
    df["upper_ema"] = ema(df["upper"].fillna(0.0), length=ema_length)
    df["lower_ema"] = ema(df["lower"].fillna(0.0), length=ema_length)
    df["rvi"] = df["upper_ema"] / (df["upper_ema"] + df["lower_ema"]) * 100
    return df["rvi"]
