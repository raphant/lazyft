"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
# --- Do not remove these libs ---
import json
import pathlib
import sys
from datetime import datetime, timedelta
from functools import reduce

import rapidjson
import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import RealParameter, IntParameter, CategoricalParameter
from freqtrade.strategy.interface import IStrategy
from freqtrade.persistence import Trade
from rich import print
from custom_util import load


class TestStrategy(IStrategy):
    # Stoploss:
    stoploss = -0.1

    # ROI table:
    minimal_roi = {"0": 0.1}

    # endregion

    ticker_interval = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sell'] = 0
        return dataframe
