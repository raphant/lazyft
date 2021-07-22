# --- Do not remove these libs ---
from freqtradestrategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

# --------------------------------
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


class ADXMomentum(IStrategy):
    """

    author@: Gert Wohlgemuth

    converted from:

        https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/AdxMomentum.cs

    """

    minimal_roi = minimal_roi

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = stoploss

    locals().update(trailing_params)

    # Optimal ticker interval for the strategy
    timeframe = '1h'

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 20

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=25)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=25)
        dataframe['sar'] = ta.SAR(dataframe)
        dataframe['mom'] = ta.MOM(dataframe, timeperiod=14)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] > 25)
                & (dataframe['mom'] > 0)
                & (dataframe['minus_di'] > 25)
                & (dataframe['plus_di'] > dataframe['minus_di'])
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] > 25)
                & (dataframe['mom'] < 0)
                & (dataframe['minus_di'] > 25)
                & (dataframe['plus_di'] < dataframe['minus_di'])
            ),
            'sell',
        ] = 1
        return dataframe
