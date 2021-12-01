import logging

# --- Do not remove these libs ---
from functools import reduce

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.strategy import (
    merge_informative_pair,
)
from freqtrade.strategy.hyper import BaseParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame

from indicatormix import populator, condition_tools
from indicatormix.advanced_optimizer import AdvancedOptimizer

logger = logging.getLogger(__name__)

load = True
if __name__ == '':
    load = False

buy_params = {
    "buy_comparison_series_1": "bb_fast__bb_upperband",  # value loaded from strategy
    "buy_comparison_series_2": "low",  # value loaded from strategy
    "buy_comparison_series_3": "wma_fast_1h__WMA",  # value loaded from strategy
    "buy_operator_1": "<=",  # value loaded from strategy
    "buy_operator_2": "<",  # value loaded from strategy
    "buy_operator_3": "<=",  # value loaded from strategy
    "buy_series_1": "sma_fast__SMA",  # value loaded from strategy
    "buy_series_2": "rsi__rsi",  # value loaded from strategy
    "buy_series_3": "atr_1h__atr",  # value loaded from strategy
}
sell_params = {
    "sell_comparison_series_1": "ema_slow__EMA",  # value loaded from strategy
    "sell_comparison_series_2": "bb_fast__bb_lowerband",  # value loaded from strategy
    "sell_comparison_series_3": "open",  # value loaded from strategy
    "sell_comparison_series_4": "bb_fast_1h__bb_middleband",  # value loaded from strategy
    "sell_comparison_series_5": "vwap__vwap",  # value loaded from strategy
    "sell_comparison_series_6": "hema_fast_1h__hma",  # value loaded from strategy
    "sell_operator_1": "<=",  # value loaded from strategy
    "sell_operator_2": ">",  # value loaded from strategy
    "sell_operator_3": ">=",  # value loaded from strategy
    "sell_operator_4": "<",  # value loaded from strategy
    "sell_operator_5": "crossed_below",  # value loaded from strategy
    "sell_operator_6": "<=",  # value loaded from strategy
    "sell_series_1": "ema_slow_30m__EMA",  # value loaded from strategy
    "sell_series_2": "bb_fast_30m__bb_upperband",  # value loaded from strategy
    "sell_series_3": "ema_fast__EMA",  # value loaded from strategy
    "sell_series_4": "supertrend_fast__supertrend",  # value loaded from strategy
    "sell_series_5": "bb_fast_1h__bb_middleband",  # value loaded from strategy
    "sell_series_6": "bb_slow_1h__bb_lowerband",  # value loaded from strategy
}


class IndicatorMixAdvancedOpt(IStrategy):
    # region config
    n_buy_conditions_per_group = 0
    n_sell_conditions_per_group = 3
    # endregion
    # region Parameters
    if load:
        ao = AdvancedOptimizer(buy_params, sell_params, optimize_timeperiods=False)
        # ao.add_comparison_group(buy_params1, 'buy')
        # ao.add_comparison_group(buy_params2, 'buy')
        # ao.add_comparison_group(buy_params3, 'buy')
        locals().update(ao.create_parameters())

    # endregion
    # region Params
    # buy_params = {
    #     "buy_series_1": "supertrend_fast__supertrend",
    #     "buy_series_2": "supertrend_slow__supertrend",
    # }
    # ROI table:
    minimal_roi = {"0": 0.179, "32": 0.056, "68": 0.026, "177": 0}

    # Stoploss:
    stoploss = -0.267
    # endregion
    timeframe = '5m'
    use_custom_stoploss = False

    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def informative_pairs(self) -> ListPairsWithTimeframes:
        pairs = self.dp.current_whitelist()
        # get each timeframe from inf_timeframes
        return [
            (pair, timeframe)
            for pair in pairs
            for timeframe in self.ao.state.indicator_depot.inf_timeframes
        ]

    def populate_informative_indicators(self, dataframe: DataFrame, metadata):
        inf_dfs = {}
        for timeframe in self.ao.state.indicator_depot.inf_timeframes:
            inf_dfs[timeframe] = self.dp.get_pair_dataframe(
                pair=metadata['pair'], timeframe=timeframe
            )
        for indicator in self.ao.indicators.values():
            if not indicator.informative:
                continue
            inf_dfs[indicator.timeframe] = populator.populate(
                self.ao.state, indicator.name, inf_dfs[indicator.timeframe]
            )
        for tf, df in inf_dfs.items():
            dataframe = merge_informative_pair(dataframe, df, self.timeframe, tf)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for indicator in self.ao.indicators.values():
            if indicator.informative:
                continue
            try:
                dataframe = populator.populate_with_hyperopt(
                    self.ao.state, indicator.name, dataframe
                )
            except Exception as e:
                logger.error(f"Error populating {indicator.name}: {e}")
                raise e
        dataframe = self.populate_informative_indicators(dataframe, metadata)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'buy_tag'] = ''
        local_parameters = {
            k: v
            for k, v in self.__class__.__dict__.items()
            if isinstance(v, BaseParameter)
        }
        conditions = self.ao.create_conditions(
            dataframe, local_parameters, 'buy', self.n_buy_conditions_per_group
        )
        if conditions:
            if self.n_buy_conditions_per_group > 0:
                dataframe = condition_tools.label_tags(
                    dataframe, conditions, 'buy_tag', self.n_buy_conditions_per_group
                )
                # replace empty tags with None
                dataframe.loc[reduce(lambda x, y: x | y, conditions), 'buy'] = 1
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        dataframe['buy_tag'] = dataframe['buy_tag'].replace('', None)
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_tag'] = ''
        local_parameters = {
            k: v
            for k, v in self.__class__.__dict__.items()
            if isinstance(v, BaseParameter)
        }
        conditions = self.ao.create_conditions(
            dataframe, local_parameters, 'sell', self.n_sell_conditions_per_group
        )

        if conditions:
            if self.n_sell_conditions_per_group > 0:
                dataframe = condition_tools.label_tags(
                    dataframe, conditions, 'exit_tag', self.n_sell_conditions_per_group
                )
                dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
            # if sell_comparisons_per_group does not equal 1, then any group in the conditions
            # can be True to generate a sell signal
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe
