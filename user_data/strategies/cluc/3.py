"""
    395 trades.
    253/137/5 Wins/Draws/Losses.
    Avg profit   1.33%.
    Median profit   1.37%.
    Total profit  0.04646295 BTC ( 523.89Σ%).
    Avg duration 184.1 min.
    Objective: -2557.33518

    # Back testing
    =============== SUMMARY METRICS ===============
    | Metric                | Value               |
    |-----------------------+---------------------|
    | Backtesting from      | 2020-08-06 00:00:00 |
    | Backtesting to        | 2020-08-25 20:21:00 |
    | Total trades          | 64                  |
    | First trade           | 2020-08-06 08:27:00 |
    | First trade Pair      | ANKR/BTC            |
    | Total Profit %        | 64.58%              |
    | Trades per day        | 3.37                |
    | Best day              | 20.12%              |
    | Worst day             | -4.45%              |
    | Days win/draw/lose    | 14 / 4 / 2          |
    | Avg. Duration Winners | 0:10:00             |
    | Avg. Duration Loser   | 0:20:00             |
    | Max Drawdown          | 14.46%              |
    | Drawdown Start        | 2020-08-13 09:22:00 |
    | Drawdown End          | 2020-08-13 21:03:00 |
    | Market change         | 21.44%              |
    ===============================================

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
minimal_roi = {"0": 0.05517, "8": 0.02, "15": 0.01367, "30": 0}

# Stoploss:
stoploss = -0.14453

# Trailing stop:
trailing_params = {
    'trailing_only_offset_is_reached': False,
    'trailing_stop': True,
    'trailing_stop_positive': 0.24219,
    'trailing_stop_positive_offset': 0.28665,
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
    ticker_interval = '1m'

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
