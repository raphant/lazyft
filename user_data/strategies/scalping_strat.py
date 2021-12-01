# --- Do not remove these libs ---
import sys
import time
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import Optional, Union

import talib.abstract as ta
from freqtrade.exchange import timeframe_to_prev_date
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import pandas_ta as pta
from technical import qtpylib

sys.path.append(str(Path(__file__).parent))

import custom_indicators as cta

# --------------------------------


class ScalpingStrategy(IStrategy):

    # region Params
    stoploss = -0.30
    # endregion
    minimal_roi = {"0": 0.01}

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    use_custom_stoploss = False
    custom_roi = {}
    custom_stoploss_dict = {}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ohlc = cta.heiken_ashi(dataframe)
        dataframe = dataframe.assign(**ohlc)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=5)
        dataframe['atr_ts1'] = dataframe['close'] - (3 * dataframe['atr'])
        dataframe['atr_ts2'] = dataframe['atr_ts1'].cummax()
        dataframe = dataframe.join(cta.supertrend(dataframe, multiplier=3, period=5))
        dataframe['color'] = cta.chop_zone(dataframe, 30)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append((dataframe['supertrend_crossed_up']))
        conditions.append(dataframe['close'] > dataframe['atr_ts1'])
        conditions.append(
            dataframe['color'].str.contains('turquoise|dark_green|pale_green')
        )
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # conditions.append((dataframe['supertrend_crossed_down']))
        # conditions.append(dataframe['color'].str.contains('red|dark_red|orange'))
        # conditions.append(
        #     qtpylib.crossed_below(dataframe['close'], dataframe['atr_ts2'])
        # )

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe

    # def min_roi_reached(
    #     self, trade: Trade, current_profit: float, current_time: datetime
    # ) -> bool:
    #     if current_profit > self.custom_roi[trade.pair]:
    #         return True
    #     return super().min_roi_reached(trade, current_profit, current_time)

    # def confirm_trade_entry(
    #     self,
    #     pair: str,
    #     order_type: str,
    #     amount: float,
    #     rate: float,
    #     time_in_force: str,
    #     current_time: datetime,
    #     **kwargs,
    # ) -> bool:
    #     # Obtain pair dataframe.
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     # Obtain last available candle. Do not use current_time to look up latest candle, because
    #     # current_time points to current incomplete candle whose data is not available.
    #     last_candle = dataframe.iloc[-1].squeeze()
    #     # trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
    #     self.custom_stoploss_dict[pair] = last_candle['atr_ts1']
    #     self.custom_roi[pair] = rate * 1.15
    #     return super().confirm_trade_entry(
    #         pair, order_type, amount, rate, time_in_force, current_time, **kwargs
    #     )

    # def custom_sell(
    #     self,
    #     pair: str,
    #     trade: Trade,
    #     current_time: datetime,
    #     current_rate: float,
    #     current_profit: float,
    #     **kwargs,
    # ) -> Optional[Union[str, bool]]:
    #     # Obtain pair dataframe.
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     # Obtain last available candle. Do not use current_time to look up latest candle, because
    #     # current_time points to current incomplete candle whose data is not available.
    #     last_candle = dataframe.iloc[-1].squeeze()
    #     trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
    #     trade_candle = dataframe.loc[dataframe['date'] == trade_date]
    #     if not trade_candle.empty:
    #         trade_candle = trade_candle.squeeze()
    #         if current_rate <= trade_candle['atr_ts1']:
    #             return 'atr_ts1'

    # def confirm_trade_exit(
    #     self,
    #     pair: str,
    #     trade: Trade,
    #     order_type: str,
    #     amount: float,
    #     rate: float,
    #     time_in_force: str,
    #     sell_reason: str,
    #     current_time: datetime,
    #     **kwargs,
    # ) -> bool:
    #     self.custom_roi.pop(pair, None)
    #     self.custom_stoploss_dict.pop(pair, None)
    #     return True

    # def custom_sell(
    #     self,
    #     pair: str,
    #     trade: Trade,
    #     current_time: datetime,
    #     current_rate: float,
    #     current_profit: float,
    #     **kwargs,
    # ) -> Optional[Union[str, bool]]:
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     last_candle = dataframe.iloc[-1].squeeze()
    #     last_2_candles = dataframe.iloc[-2:-1].squeeze()
    #     time_elapsed = current_time - trade.open_date
    #     if time_elapsed.total_seconds() > 60 * 60:
    #         crossed_above = qtpylib.crossed_above(
    #             last_2_candles['sar'], dataframe['bb_mid']
    #         )
    #         if crossed_above:
    #             return 'adjusted-signal'
    #     else:
    #         crossed_above = qtpylib.crossed_above(
    #             last_2_candles['sar'], dataframe['bb_upper']
    #         )
    #         if crossed_above:
    #             return 'sell-signal'
