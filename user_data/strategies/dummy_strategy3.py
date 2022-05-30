"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
# --- Do not remove these libs ---
from datetime import datetime
from typing import Optional, Union

import pandas_ta
from finta import TA as ta
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame


class TestStrategy3(IStrategy):
    # Stoploss:
    stoploss = -0.99
    exit_sell_signal = True
    # ROI table:
    sell_profit_only = True
    minimal_roi = {"0": 0.01}
    ignore_roi_if_buy_signal = False
    # endregion

    ticker_interval = "5m"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["buy"] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sell"] = 0
        return dataframe
