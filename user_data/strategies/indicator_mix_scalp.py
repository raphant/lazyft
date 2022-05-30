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
# import talib as ta
#
# sys.path.append(str(Path(__file__).parent))
# sys.path.append(str(Path(__file__).parent.joinpath('indicatormix')))
# from indicatormix.indicator_opt import IndicatorOptHelper, indicators
# import custom_indicators as cta
#
#
# logger = logging.getLogger(__name__)
#
# load = True
# if __name__ == '':
#     load = False
#
#
# class IndicatorMixScalp(IStrategy):
#     # region Parameters
#     if load:
#         iopt = IndicatorOptHelper.get()
#         buy_comparisons, sell_comparisons = iopt.create_local_parameters(
#             locals(), num_buy=8, num_sell=4
#         )
#     # endregion
#     # region Params
#     # Sell hyperspace params:
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
#     # minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
#     stoploss = -0.25
#     # endregion
#     timeframe = '5m'
#     use_custom_stoploss = False
#
#     buy_comparisons_per_group = 4
#     sell_comparisons_per_group = 2
#
#     # Recommended
#     exit_sell_signal = True
#     sell_profit_only = False
#     ignore_roi_if_buy_signal = True
#     startup_candle_count = 200
#
#     def __init__(self, config: dict) -> None:
#         super().__init__(config)
#
#     def informative_pairs(self) -> ListPairsWithTimeframes:
#         pairs = self.dp.current_whitelist()
#         # get each timeframe from inf_timeframes
#         return [
#             (pair, timeframe)
#             for pair in pairs
#             for timeframe in self.iopt.inf_timeframes
#         ]
#
#     def populate_informative_indicators(self, dataframe: DataFrame, metadata):
#         inf_dfs = {}
#         for timeframe in self.iopt.inf_timeframes:
#             inf_dfs[timeframe] = self.dp.get_pair_dataframe(
#                 pair=metadata['pair'], timeframe=timeframe
#             )
#         for indicator in indicators.values():
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
#         for indicator in indicators.values():
#             if indicator.informative:
#                 continue
#             dataframe = indicator.populate(dataframe)
#         dataframe = self.populate_informative_indicators(dataframe, metadata)
#         # ohlc = cta.heiken_ashi(dataframe)
#         # dataframe = dataframe.assign(**ohlc)
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
#         conditions = self.iopt.create_conditions(
#             dataframe=dataframe,
#             comparison_parameters=self.sell_comparisons,
#             strategy=self,
#             bs='sell',
#             n_per_group=self.sell_comparisons_per_group,
#         )
#         if conditions:
#             # if sell_comparisons_per_group equals 1, then all conditions will have to be true
#             # for a sell signal
#             if self.sell_comparisons_per_group == 1:
#                 dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
#             # if sell_comparisons_per_group does not equal 1, then any group in the conditions
#             # can be True to generate a sell signal
#             else:
#                 dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
#         return dataframe
