"""
    2189 trades.
    1280/143/766 Wins/Draws/Losses.
    Avg profit   0.55%.
    Median profit   1.27%.
    Total profit  0.10717258 BTC ( 1208.42Σ%).
    Avg duration 1000.7 min.
    Objective: -33.51296

"""

# --- Do not remove these libs ---
from freqtradestrategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtradevendor.qtpylib.indicators as qtpylib

# --------------------------------

# ROI table:
minimal_roi = {"0": 0.4291, "304": 0.15516, "890": 0.03486, "1551": 0}

# Stoploss:
stoploss = -0.34366

# Trailing stop:
trailing_params = {
    'trailing_only_offset_is_reached': True,
    'trailing_stop': True,
    'trailing_stop_positive': 0.01039,
    'trailing_stop_positive_offset': 0.02276,
}


class AdxSmasBT(IStrategy):
    """

    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/AdxSmas.cs

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
        dataframe['short'] = ta.SMA(dataframe, timeperiod=3)
        dataframe['long'] = ta.SMA(dataframe, timeperiod=6)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] > 25)
                & (qtpylib.crossed_above(dataframe['short'], dataframe['long']))
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] < 25)
                & (qtpylib.crossed_above(dataframe['long'], dataframe['short']))
            ),
            'sell',
        ] = 1
        return dataframe
