"""
    71/100:    629 trades. Avg profit   0.93%. Total profit  0.05210743 BTC ( 587.53Σ%). Avg duration  35.7 min. Objective: -54.29047
    trailing
    """
# --- Do not remove these libs ---
from freqtradestrategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame

# --------------------------------

import talib.abstract as ta
import freqtradevendor.qtpylib.indicators as qtpylib
from typing import Dict, List
from functools import reduce
from pandas import DataFrame, DatetimeIndex, merge

# --------------------------------

import talib.abstract as ta
import freqtradevendor.qtpylib.indicators as qtpylib
import numpy  # noqa

# ROI table:
minimal_roi = {"0": 0.0614, "25": 0.0469, "82": 0.03602, "131": 0}

# Stoploss:
stoploss = -0.21976

# Trailing stop:
trailing_params = {
    'trailing_only_offset_is_reached': True,
    'trailing_stop': True,
    'trailing_stop_positive': 0.03831,
    'trailing_stop_positive_offset': 0.11323,
}


class Cluc(IStrategy):
    """

    author@: Gert Wohlgemuth

    works on new objectify branch!

    """

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = minimal_roi

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = stoploss

    locals().update(trailing_params)
    # Optimal ticker interval for the strategy
    ticker_interval = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=5)
        rsiframe = DataFrame(dataframe['rsi']).rename(columns={'rsi': 'close'})
        dataframe['emarsi'] = ta.EMA(rsiframe, timeperiod=5)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['adx'] = ta.ADX(dataframe)
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['ema100'])
                & (dataframe['close'] < 0.985 * dataframe['bb_lowerband'])
                & (
                    dataframe['volume']
                    < (dataframe['volume'].rolling(window=30).mean().shift(1) * 20)
                )
            ),
            'buy',
        ] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[((dataframe['close'] > dataframe['bb_middleband'])), 'sell'] = 1
        return dataframe
