# --- Do not remove these libs ---
import freqtradevendor.qtpylib.indicators as qtpylib
import numpy  # noqa

# --------------------------------
import talib.abstract as ta
from freqtradestrategy.interface import IStrategy

# --------------------------------
from pandas import DataFrame

# ROI table:
minimal_roi = {"0": 0.06102, "8": 0.03648, "20": 0.01212, "42": 0}

# Stoploss:
stoploss = -0.25

# Trailing stop:
trailing_params = {
    'trailing_only_offset_is_reached': True,
    'trailing_stop': True,
    'trailing_stop_positive': 0.17356,
    'trailing_stop_positive_offset': 0.24957,
}


class Scalp(IStrategy):
    """
    this strategy is based around the idea of generating a lot of
    potentials buys and make tiny profits on each trade

    we recommend to have at least 60 parallel trades at any time to cover
    non avoidable losses.

    Recommended is to only sell based on ROI for this strategy
    """

    minimal_roi = minimal_roi

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = stoploss

    locals().update(trailing_params)

    # Optimal ticker interval for the strategy
    # the shorter the better
    ticker_interval = '1m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=5, price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=5, price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=5, price='low')
        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        dataframe['adx'] = ta.ADX(dataframe)

        # required for graphing
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['open'] < dataframe['ema_low'])
                & (dataframe['adx'] > 30)
                & (
                    (dataframe['fastk'] < 30)
                    & (dataframe['fastd'] < 30)
                    & (qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']))
                )
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            ((dataframe['open'] >= dataframe['ema_high']))
            | (
                (qtpylib.crossed_above(dataframe['fastk'], 70))
                | (qtpylib.crossed_above(dataframe['fastd'], 70))
            ),
            'sell',
        ] = 1
        return dataframe
