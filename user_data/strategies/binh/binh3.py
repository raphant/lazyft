"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
# --- Do not remove these libs ---

from functools import reduce

import talib.abstract as ta
from pandas import DataFrame

import freqtradevendor.qtpylib.indicators as qtpylib
from freqtradestrategy import RealParameter, IntParameter, CategoricalParameter
from ft.strategy.interface import IStrategy


# --------------------------------


# noinspection DuplicatedCode
class BinH3(IStrategy):
    """
    556 trades. 348/194/14 Wins/Draws/Losses. Avg profit   1.88%.
    Median profit   1.30%. Total profit  1046.77706433 USD ( 209.36Σ%).
    Avg duration 9:10:00 min. Objective: -51.14341
    """

    # region Buy Hyperopt
    buy_bb_lower = RealParameter(-1.0, 3.0, default=2.0, space='buy')
    buy_bbdelta_close = RealParameter(0.001, 0.015, default=0.07, space='buy')
    buy_closedelta_close = RealParameter(0.001, 0.03, default=0.01, space='buy')
    buy_tail_bbdelta = RealParameter(0.01, 0.4, default=0.2, space='buy')
    # endregion

    # region Sell Hyperopt
    sell_mfi = IntParameter(75, 100, default=80, space='sell')
    sell_mfi_enabled = CategoricalParameter([True, False], space='sell')

    # endregion

    # region Params
    # Buy hyperspace params:
    buy_params = {
        "buy_bb_lower": -0.94662,
        "buy_bbdelta_close": 0.00315,
        "buy_closedelta_close": 0.02977,
        "buy_tail_bbdelta": 0.10643,
    }

    # Sell hyperspace params:
    sell_params = {
        "sell_mfi": 100,
        "sell_mfi_enabled": True,
    }

    # Stoploss:
    stoploss = -0.274

    # trailing stop loss
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.058
    trailing_only_offset_is_reached = False

    # ROI table:
    minimal_roi = {"0": 0.175, "21": 0.053, "75": 0.013, "118": 0}
    # endregion

    ticker_interval = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Replace NaN with zero and infinity with large finite numbers
        # https://numpy.org/doc/stable/reference/generated/numpy.nan_to_num.html
        dataframe['mfi'] = ta.MFI(dataframe)

        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)

        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_upperband'] = bollinger['upperband']
        # Delta = bb_middleband - bb_lowerband
        dataframe['bbdelta'] = (
            dataframe['bb_middleband'] - dataframe['bb_lowerband']
        ).abs()
        dataframe['pricedelta'] = (dataframe['open'] - dataframe['close']).abs()
        dataframe['closedelta'] = (
            dataframe['close'] - dataframe['close'].shift()
        ).abs()
        dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs()
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # GUARDS AND TRENDS
        if self.buy_bb_lower.value:
            conditions.append(
                dataframe['bb_lowerband'].shift().gt(self.buy_bb_lower.value)
            )
        if self.buy_bbdelta_close.value:
            conditions.append(
                dataframe['bbdelta'].gt(
                    dataframe['close'] * self.buy_bbdelta_close.value
                )
            )
        if self.buy_closedelta_close.value:
            conditions.append(
                dataframe['closedelta'].gt(
                    dataframe['close'] * self.buy_closedelta_close.value
                )
            )
        if self.buy_tail_bbdelta:
            conditions.append(
                dataframe['tail']
                .shift()
                .lt(dataframe['bbdelta'] * self.buy_tail_bbdelta.value)
            )

        # # TRIGGERS
        # if 'trigger' in params:
        #     if params['trigger'] == 'bb_lower':
        #         conditions.append(
        #             dataframe['close'] < dataframe['bb_lowerband'])
        #     if params['trigger'] == 'macd_cross_signal':
        #         conditions.append(qtpylib.crossed_above(
        #             dataframe['macd'], dataframe['macdsignal']
        #         ))

        # Check that the candle had volume
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        no sell signal
        """
        conditions = []

        # GUARDS AND TRENDS
        if self.sell_mfi_enabled.value:
            conditions.append(dataframe['mfi'] > self.sell_mfi.value)

        # TRIGGERS
        conditions.append(
            qtpylib.crossed_above(dataframe['macdsignal'], dataframe['macd'])
        )

        # Check that the candle had volume
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1

        return dataframe
