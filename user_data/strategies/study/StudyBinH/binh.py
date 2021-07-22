"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
# --- Do not remove these libs ---
import json
import pathlib
from datetime import datetime, timedelta
from functools import reduce

import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import RealParameter, IntParameter, CategoricalParameter
from freqtrade.strategy.interface import IStrategy
from freqtrade.persistence import Trade

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.absolute()


# --------------------------------


# noinspection DuplicatedCode
param_file_id = 'vPBfxP'
params_file = pathlib.Path(SCRIPT_DIRECTORY, 'params.json')


def load():
    if '$' in param_file_id or not params_file.exists():
        return {}
    params = json.loads(params_file.read_text())
    return params['StudyBinH'][param_file_id]['params']


class StudyBinH(IStrategy):
    """
    556 trades. 348/194/14 Wins/Draws/Losses. Avg profit   1.88%.
    Median profit   1.30%. Total profit  1046.77706433 USD ( 209.36Σ%).
    Avg duration 9:10:00 min. Objective: -51.14341
    """

    # region Buy Hyperopt
    buy_bb_lower = RealParameter(-3.0, 5.0, default=2.0, space='buy')
    buy_bbdelta_close = RealParameter(0.001, 0.015, default=0.07, space='buy')
    buy_closedelta_close = RealParameter(0.001, 0.03, default=0.01, space='buy')
    buy_tail_bbdelta = RealParameter(0.01, 0.5, default=0.2, space='buy')
    # endregion

    # region Sell Hyperopt
    sell_mfi = IntParameter(70, 100, default=80, space='sell')
    sell_mfi_enabled = CategoricalParameter([True, False], default=True, space='sell')
    # endregion

    # region Params
    stoploss = -0.25

    locals().update(load())

    # endregion

    ticker_interval = '5m'

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
