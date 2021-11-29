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
#
#
# # Buy hyperspace params:
# buy_params = {
#     "buy_comparison_series_1": "zema_1h__zema",  # value loaded from strategy
#     "buy_comparison_series_2": "close",  # value loaded from strategy
#     "buy_comparison_series_3": "t3_30m__T3Average",  # value loaded from strategy
#     "buy_comparison_series_4": "tema_slow_1h__TEMA",  # value loaded from strategy
#     "buy_comparison_series_5": "wma_slow__WMA",  # value loaded from strategy
#     "buy_comparison_series_6": "bb_fast__bb_upperband",  # value loaded from strategy
#     "buy_comparison_series_7": "wma_fast_30m__WMA",  # value loaded from strategy
#     "buy_comparison_series_8": "ema_slow_1h__EMA",  # value loaded from strategy
#     "buy_operator_1": "crossed_below",  # value loaded from strategy
#     "buy_operator_2": ">=",  # value loaded from strategy
#     "buy_operator_3": "crossed_above",  # value loaded from strategy
#     "buy_operator_4": ">",  # value loaded from strategy
#     "buy_operator_5": "<",  # value loaded from strategy
#     "buy_operator_6": "crossed_above",  # value loaded from strategy
#     "buy_operator_7": ">=",  # value loaded from strategy
#     "buy_operator_8": "<=",  # value loaded from strategy
#     "buy_series_1": "stoch_sma_30m__stoch_sma",  # value loaded from strategy
#     "buy_series_2": "bb_fast_30m__bb_lowerband",  # value loaded from strategy
#     "buy_series_3": "zema_1h__zema",  # value loaded from strategy
#     "buy_series_4": "bb_fast_30m__bb_lowerband",  # value loaded from strategy
#     "buy_series_5": "bb_slow_1h__bb_lowerband",  # value loaded from strategy
#     "buy_series_6": "rsi__rsi",  # value loaded from strategy
#     "buy_series_7": "tema_slow_30m__TEMA",  # value loaded from strategy
#     "buy_series_8": "bb_fast_1h__bb_upperband",  # value loaded from strategy
# }
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
# else:
#     ct = CombinationTester(buy_params, sell_params)
#     iopt = ct.iopt
#
#
# class IMTest(IStrategy):
#     # region Parameters
#     if load:
#         ct.update_local_parameters(locals())
#     # endregion
#     # region Params
#     minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
#     stoploss = -0.25
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
#             inf_dfs[indicator.timeframe] = indicator.populate_with_ranges(
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
#             dataframe = indicator.populate_with_ranges(dataframe)
#         dataframe = self.populate_informative_indicators(dataframe, metadata)
#
#         return dataframe
#
#     def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         conditions = []
#         for c in ct.buy_comparisons:
#             parameter_name = self.ct.get_parameter_name(c.series1.series_name)
#             parameter = getattr(self, parameter_name, None)
#             conditions.append(
#                 self.ct.compare(
#                     data=dataframe,
#                     comparison=c,
#                     bs='buy',
#                     strategy_locals=locals().copy(),
#                     optimized_parameter=parameter,
#                 )
#             )
#         if conditions:
#             dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
#         return dataframe
#
#     def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         conditions = []
#         for c in ct.sell_comparisons:
#             parameter_name = self.ct.get_parameter_name(c.series1.series_name)
#             parameter = getattr(self, parameter_name, None)
#             conditions.append(
#                 self.ct.compare(
#                     data=dataframe,
#                     comparison=c,
#                     bs='sell',
#                     optimized_parameter=parameter,
#                 )
#             )
#         if conditions:
#             dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
#         return dataframe
#
#
# class IMTestOpt(IStrategy):
#     # region Parameters
#     # ct
#     ct.update_local_parameters(locals())
#
#     # sell
#     _, sell_parameters = ct.iopt.create_local_parameters(locals(), num_sell=3)
#     # endregion
#     # region Params
#     minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
#     stoploss = -0.25
#     # Buy hyperspace params:
#     buy_params = {
#         "ewo__ewo__buy_value": 1.764,
#         "stoch_sma__stoch80_sma10__buy_value": 44,
#     }
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
#
#         return dataframe
#
#     def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         # conditions = iopt.create_conditions(dataframe, self.buy_parameters, self, 'buy')
#
#         conditions = ct.get_conditions(dataframe, self, 'buy')
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
