# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame, Series, concat

# --------------------------------
from freqtrade.strategy import (
    merge_informative_pair,
    DecimalParameter,
    IntParameter,
    CategoricalParameter,
)
import numpy as np

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class TTF(IStrategy):
    """Tradingview heikin ashi smoothed v4
    author@:
    """

    INTERFACE_VERSION = 2
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {"0": 10}

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.9

    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'

    # trailing stoploss
    trailing_stop = False
    trailing_only_offset_is_reached = False
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03

    # run "populate_indicators" only for new candle
    process_only_new_candles = True

    # Experimental settings (configuration will overide these if set)
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True

    ttf_length = IntParameter(1, 50, default=15)
    ttf_upperTrigger = IntParameter(1, 400, default=100)
    ttf_lowerTrigger = IntParameter(1, -400, default=-100)
    from pathlib import Path
    import sys

    sys.path.append(str(Path(__file__).parent))
    from util import load

    if locals()['__module__'] == locals()['__qualname__']:
        locals().update(load(locals()['__qualname__']))

    # Optional order type mapping
    order_types = {
        'buy': 'limit',
        'sell': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False,
    }

    def get_ticker_indicator(self):
        return int(self.timeframe[:-1])

    def informative_pairs(self):
        # get access to all pairs available in whitelist.
        pairs = self.dp.current_whitelist()
        # Assign tf to each pair so they can be downloaded and cached for strategy.
        informative_pairs = [(pair, '1h') for pair in pairs]
        return informative_pairs

    def informative_1h_indicators(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:
        assert self.dp, "DataProvider is required for multiple timeframes."
        # Get the informative pair
        informative_1h = self.dp.get_pair_dataframe(
            pair=metadata['pair'], timeframe=self.inf_1h
        )

        # Heikin Ashi Smoothed V4
        informative_1h['ttf'] = ttf(informative_1h, int(self.ttf_length.value))

        return informative_1h

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        informative_1h = self.informative_1h_indicators(dataframe, metadata)
        dataframe = merge_informative_pair(
            dataframe, informative_1h, self.timeframe, self.inf_1h, ffill=True
        )

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(
            (
                (
                    qtpylib.crossed_above(
                        dataframe['ttf_1h'], self.ttf_lowerTrigger.value
                    )
                )
                & (dataframe['volume'] > 0)
            )
        )
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(
            (
                (
                    qtpylib.crossed_below(
                        dataframe['ttf_1h'], self.ttf_upperTrigger.value
                    )
                )
                & (dataframe['volume'] > 0)
            )
        )
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
        return dataframe


def ttf(df, ttf_length):
    df = df.copy()
    high, low = df['high'], df['low']
    buyPower = (
        high.rolling(ttf_length).max()
        - low.shift(ttf_length).fillna(99999).rolling(ttf_length).min()
    )
    sellPower = (
        high.shift(ttf_length).fillna(0).rolling(ttf_length).max()
        - low.rolling(ttf_length).min()
    )

    ttf = 200 * (buyPower - sellPower) / (buyPower + sellPower)
    return Series(ttf, name='ttf')
