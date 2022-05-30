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


class RBRI(IStrategy):
    """
    Rob Booker Reversal Indicator
    """

    # region Parameters
    stock_buy = IntParameter(1, 50, default=30, space="buy")
    stock_candles = IntParameter(60, 80, default=70, space="buy")
    stock_sell = IntParameter(50, 100, default=70, space="sell")
    # conditions

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

    @property
    def is_live_or_dry(self):
        return self.config["runmode"].value in ("live", "dry_run")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]
        if not self.is_live_or_dry:
            for s in self.stock_candles.range:
                stoch = qtpylib.stoch(dataframe, s)
                dataframe[f"stoch_{s}_sma10"] = qtpylib.sma(
                    (stoch["slow_k"] + stoch["slow_d"]) / 2, 10
                )
        else:
            stoch = qtpylib.stoch(dataframe, self.stock_candles.value)
            dataframe[f"stoch_{self.stock_candles.value}_sma10"] = qtpylib.sma(
                (stoch["slow_k"] + stoch["slow_d"]) / 2, 10
            )

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            (
                qtpylib.crossed_above(
                    dataframe["macdsignal"], pd.Series(np.zeros(len(dataframe)))
                )
            )
            & (
                qtpylib.crossed_below(
                    dataframe[f"stoch_{self.stock_candles.value}_sma10"],
                    self.stock_buy.value,
                )
            )
        ]
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "buy"] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            (dataframe["macdsignal"] < 0)
            & (
                dataframe[f"stoch_{self.stock_candles.value}_sma10"]
                > self.stock_sell.value
            )
        ]
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
