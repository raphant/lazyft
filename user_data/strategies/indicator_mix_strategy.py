import logging

# --- Do not remove these libs ---
from functools import reduce

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.strategy import merge_informative_pair
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame

from indicatormix import parameter_tools, condition_tools, populator
from indicatormix.main import IndicatorMix

logger = logging.getLogger(__name__)

load = True
if __name__ == '':
    load = False


class IndicatorMixStrategy(IStrategy):
    # region config
    num_of_buy_conditions = 8
    num_of_sell_conditions = 6

    n_buy_conditions_per_group = 4
    n_sell_conditions_per_group = 3
    # endregion
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
        # group1
        "sell_series_1": "ema_slow_30m__EMA",
        "sell_series_2": "bb_fast_30m__bb_upperband",
        "sell_series_3": "ema_fast__EMA",
        "sell_operator_1": "<=",
        "sell_operator_2": ">",
        "sell_operator_3": ">=",
        "sell_comparison_series_1": "ema_slow__EMA",
        "sell_comparison_series_2": "bb_fast__bb_lowerband",
        "sell_comparison_series_3": "open",
        # group2
        "sell_series_4": "supertrend_fast__supertrend",
        "sell_series_5": "bb_fast_1h__bb_middleband",
        "sell_series_6": "bb_slow_1h__bb_lowerband",
        "sell_operator_4": "<",
        "sell_operator_5": "crossed_below",
        "sell_operator_6": "<=",
        "sell_comparison_series_4": "bb_fast_1h__bb_middleband",
        "sell_comparison_series_5": "vwap__vwap",
        "sell_comparison_series_6": "hema_fast_1h__hma",
    }
    # region Parameters
    if load:
        im = IndicatorMix()
        im.main()
        buy_comparisons, sell_comparisons = parameter_tools.create_local_parameters(
            im.state,
            locals(),
            num_buy=num_of_buy_conditions,
            num_sell=num_of_sell_conditions,
            sell_skip_comparisons=list(range(4, 9 + 1)),
        )
    # endregion
    # region Params
    # minimal_roi = {"0": 0.05, "30": 0.03, "60": 0.01, "100": 0}
    # stoploss = -0.10

    minimal_roi = {"0": 0.179, "32": 0.056, "68": 0.026, "177": 0}
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
            for timeframe in self.im.state.indicator_depot.inf_timeframes
        ]

    def populate_informative_indicators(self, dataframe: DataFrame, metadata):
        inf_dfs = {}
        for timeframe in self.im.state.indicator_depot.inf_timeframes:
            inf_dfs[timeframe] = self.dp.get_pair_dataframe(
                pair=metadata['pair'], timeframe=timeframe
            )
        for indicator in self.im.indicators.values():
            if not indicator.informative:
                continue
            inf_dfs[indicator.timeframe] = populator.populate(
                self.im.state, indicator.name, inf_dfs[indicator.timeframe]
            )
        for tf, df in inf_dfs.items():
            dataframe = merge_informative_pair(dataframe, df, self.timeframe, tf)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for indicator in self.im.indicators.values():
            if indicator.informative:
                continue
            dataframe = populator.populate(self.im.state, indicator.name, dataframe)
        dataframe = self.populate_informative_indicators(dataframe, metadata)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'buy_tag'] = ''

        conditions = condition_tools.create_conditions(
            self.im.state,
            dataframe=dataframe,
            comparison_parameters=self.buy_comparisons,
            strategy=self,
            bs='buy',
            n_per_group=self.n_buy_conditions_per_group,
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
        dataframe.loc[:, 'buy_tag'] = dataframe['buy_tag'].replace('', None)
        dataframe.loc[dataframe['volume'] == 0, 'buy'] = 0
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_tag'] = ''
        conditions = condition_tools.create_conditions(
            self.im.state,
            dataframe=dataframe,
            comparison_parameters=self.sell_comparisons,
            strategy=self,
            bs='sell',
            n_per_group=self.n_sell_conditions_per_group,
        )

        if conditions:
            # for a sell signal
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
