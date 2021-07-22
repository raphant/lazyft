"""
    92/100:    189 trades.
    122/66/1 Wins/Draws/Losses.
    Avg profit   1.30%.
    Median profit   1.08%.
    Total profit  245.99308348 USDT ( 245.75Σ%).
    Avg duration 1130.9 min.
    Objective: -31.29108

"""
# --- Do not remove these libs ---
from freqtradestrategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
import numpy as np

# --------------------------------

import talib.abstract as ta
import freqtradevendor.qtpylib.indicators as qtpylib

# ROI table:
minimal_roi = {"0": 0.04282, "7": 0.03537, "19": 0.01083, "42": 0}

# Stoploss:
stoploss = -0.29683

# Trailing stop:
trailing_params = {
    'trailing_only_offset_is_reached': True,
    'trailing_stop': True,
    'trailing_stop_positive': 0.20038,
    'trailing_stop_positive_offset': 0.27104,
}


def bollinger_bands(stock_price, window_size, num_of_std):
    rolling_mean = stock_price.rolling(window=window_size).mean()
    rolling_std = stock_price.rolling(window=window_size).std()
    lower_band = rolling_mean - (rolling_std * num_of_std)

    return rolling_mean, lower_band


class BinH_Usdt1(IStrategy):
    minimal_roi = minimal_roi

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = stoploss

    locals().update(trailing_params)

    ticker_interval = '1m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        mid, lower = bollinger_bands(dataframe['close'], window_size=40, num_of_std=2)
        dataframe['mid'] = np.nan_to_num(mid)
        dataframe['lower'] = np.nan_to_num(lower)
        dataframe['bbdelta'] = (dataframe['mid'] - dataframe['lower']).abs()
        dataframe['pricedelta'] = (dataframe['open'] - dataframe['close']).abs()
        dataframe['closedelta'] = (
            dataframe['close'] - dataframe['close'].shift()
        ).abs()
        dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs()
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                dataframe['lower'].shift().gt(0)
                & dataframe['bbdelta'].gt(dataframe['close'] * 0.008)
                & dataframe['closedelta'].gt(dataframe['close'] * 0.0175)
                & dataframe['tail'].lt(dataframe['bbdelta'] * 0.25)
                & dataframe['close'].lt(dataframe['lower'].shift())
                & dataframe['close'].le(dataframe['close'].shift())
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        no sell signal
        """
        dataframe['sell'] = 0
        return dataframe
