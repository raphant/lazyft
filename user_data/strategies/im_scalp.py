# """
# https://kaabar-sofien.medium.com/the-catapult-indicator-innovative-trading-techniques-8910ac962c57
# """
# import logging
#
# # --- Do not remove these libs ---
# import sys
# from functools import reduce
# from pathlib import Path
#
# from freqtrade.constants import ListPairsWithTimeframes
# from freqtrade.strategy import (
#     merge_informative_pair,
# )
# from freqtrade.strategy.interface import IStrategy
# from pandas import DataFrame
#
# sys.path.append(str(Path(__file__).parent))
# from indicatormix.indicator_opt import CombinationTester, indicators
#
# logger = logging.getLogger(__name__)
# import custom_indicators as cta
# import talib as ta
#
# # Buy hyperspace params:
#
# # Sell hyperspace params:
# sell_params = {
#     "sell_comparison_series_1": "bb_slow__bb_upperband",
#     "sell_comparison_series_2": "bb_fast_1h__bb_lowerband",
#     "sell_comparison_series_3": "wma_fast_30m__WMA",
#     "sell_operator_1": ">=",
#     "sell_operator_2": "crossed_above",
#     "sell_operator_3": "crossed_below",
#     "sell_series_1": "wma_fast__WMA",
#     "sell_series_2": "ema_fast_1h__EMA",
#     "sell_series_3": "ema_slow_30m__EMA",
# }
# load = True
# if __name__ == '':
#     load = False
#
# ct = CombinationTester({}, sell_params)
# iopt = ct.iopt
#
#
# class IMScalp(IStrategy):
#     # region Parameters
#     # ct
#     ct.update_local_parameters(locals())
#
#     # sell
#     _, sell_parameters = ct.iopt.create_local_parameters(locals(), num_sell=4)
#     # endregion
#     # region Params
#     # minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
#     stoploss = -0.25
#     # Buy hyperspace params:
#     sell_params = {
#         "sell_comparison_series_1": "t3__T3Average",
#         "sell_comparison_series_2": "vwap__vwap",
#         "sell_comparison_series_3": "psar_30m__sar",
#         "sell_comparison_series_4": "hema_slow_30m__hma",
#         "sell_operator_1": "crossed_above",
#         "sell_operator_2": "crossed_above",
#         "sell_operator_3": "<=",
#         "sell_operator_4": "crossed_below",
#         "sell_series_1": "bb_slow_1h__bb_lowerband",
#         "sell_series_2": "none",
#         "sell_series_3": "rsi__rsi",
#         "sell_series_4": "hema_fast_30m__hma",
#     }
#
#     # ROI table:
#     minimal_roi = {"0": 0.204, "26": 0.069, "84": 0.038, "120": 0}
#
#     # endregion
#     timeframe = '5m'
#     use_custom_stoploss = False
#
#     # Recommended
#     use_sell_signal = True
#     sell_profit_only = False
#     ignore_roi_if_buy_signal = True
#     startup_candle_count = 200
#
#     def __init__(self, config: dict) -> None:
#         super().__init__(config)
#         self.ct = ct
#
#     def informative_pairs(self) -> ListPairsWithTimeframes:
#         pairs = self.dp.current_whitelist()
#         informative_pairs = [(pair, iopt.inf_timeframes) for pair in pairs]
#         return informative_pairs
#
#     def populate_informative_indicators(self, dataframe: DataFrame, metadata):
#         inf_dfs = {}
#         for timeframe in iopt.inf_timeframes:
#             inf_dfs[timeframe] = self.dp.get_pair_dataframe(
#                 pair=metadata['pair'], timeframe=timeframe
#             )
#         for indicator in self.ct.get_loaded_indicators():
#             if not indicator.informative:
#                 continue
#             inf_dfs[indicator.timeframe] = indicator.populate(
#                 inf_dfs[indicator.timeframe]
#             )
#         for tf, df in inf_dfs.items():
#             dataframe = merge_informative_pair(dataframe, df, self.timeframe, tf)
#         return dataframe
#
#     def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         for indicator in self.ct.get_loaded_indicators():
#             if indicator.informative:
#                 continue
#             dataframe = indicator.populate(dataframe)
#         dataframe = self.populate_informative_indicators(dataframe, metadata)
#         ohlc = cta.heiken_ashi(dataframe)
#         dataframe = dataframe.assign(**ohlc)
#         dataframe['atr'] = ta.ATR(
#             dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=5
#         )
#         dataframe['atr_ts1'] = dataframe['close'] - (3 * dataframe['atr'])
#         dataframe['atr_ts2'] = dataframe['atr_ts1'].cummax()
#         dataframe = dataframe.join(cta.supertrend(dataframe, multiplier=3, period=5))
#         dataframe['color'] = cta.chop_zone(dataframe, 30)
#         return dataframe
#
#     def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         conditions = []
#
#         conditions.append((dataframe['supertrend_crossed_up']))
#         conditions.append(dataframe['close'] > dataframe['atr_ts1'])
#         conditions.append(
#             dataframe['color'].str.contains('turquoise|dark_green|pale_green')
#         )
#         conditions.append(dataframe['volume'].gt(0))
#
#         if conditions:
#             dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
#         return dataframe
#
#     def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         # conditions = ct.get_conditions(dataframe, self, 'sell')
#         conditions = iopt.create_conditions(
#             dataframe, self.sell_parameters, self, 'sell'
#         )
#         if conditions:
#             dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
#         return dataframe
