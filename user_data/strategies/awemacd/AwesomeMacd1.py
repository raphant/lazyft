"""
    1079 trades.
    458/78/543 Wins/Draws/Losses.
    Avg profit   0.67%.
    Median profit  -0.20%.
    Total profit  0.06386748 BTC ( 720.13Σ%).
    Avg duration 1481.0 min.
    Objective: -20.75324
"""
# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

# --------------------------------
# ROI table:
minimal_roi = {"0": 0.47581, "425": 0.17035, "1060": 0.05051, "2160": 0}

# Stoploss:
stoploss = -0.26325

# Trailing stop:
trailing_params = {
    'trailing_only_offset_is_reached': False,
    'trailing_stop': True,
    'trailing_stop_positive': 0.01024,
    'trailing_stop_positive_offset': 0.05819,
}


class AwesomeMacdBT(IStrategy):
    """

    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/AwesomeMacd.cs

    """

    minimal_roi = minimal_roi

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = stoploss

    locals().update(trailing_params)

    # Optimal ticker interval for the strategy
    ticker_interval = '1h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['ao'] = qtpylib.awesome_oscillator(dataframe)

        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['macd'] > 0)
                & (dataframe['ao'] > 0)
                & (dataframe['ao'].shift() < 0)
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['macd'] < 0)
                & (dataframe['ao'] < 0)
                & (dataframe['ao'].shift() > 0)
            ),
            'sell',
        ] = 1
        return dataframe
