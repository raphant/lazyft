# --- Do not remove these libs ---
import json
from datetime import timedelta, datetime

import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import RealParameter, IntParameter
from freqtrade.strategy.interface import IStrategy
from freqtrade.persistence import Trade


# --------------------------------


class BbandRsiMod(IStrategy):
    """
    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs
    """

    # buy_bb_lower = RealParameter(-1.0, 3.0, default=2.0, space='buy')
    buy_rsi = IntParameter(5, 50, default=30, space='buy', load=True)

    sell_rsi = IntParameter(50, 100, default=70, space='sell', load=True)
    # Buy hyperspace params:
    buy_params = {
        "buy_rsi": 40,
    }

    # Sell hyperspace params:
    sell_params = {
        "sell_rsi": 67,
    }

    # Minimal ROI designed for the strategy.
    # adjust based on market conditions. We would recommend to keep it low for quick turn arounds
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {"0": 0.1}

    # Optimal stoploss designed for the strategy
    stoploss = -0.25
    use_custom_stoploss = True

    # Optimal timeframe for the strategy
    timeframe = '5m'

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> float:

        if (
            current_profit < -0.04
            and current_time - timedelta(minutes=35) > trade.open_date_utc
        ):
            return -0.01

        return -0.99

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] < self.buy_rsi.value)
                & (dataframe['close'] < dataframe['bb_lowerband'])
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['rsi'] > self.sell_rsi.value), 'sell'] = 1
        return dataframe
