import logging

# --- Do not remove these libs ---
from functools import reduce

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.strategy import (
    merge_informative_pair,
)
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame

from indicatormix.main import IndicatorMix
from indicatormix.parameter_tools import ParameterTools
from indicatormix.conditions import Conditions
from indicatormix.populator import Populator

logger = logging.getLogger(__name__)

load = True
if __name__ == '':
    load = False


class IndicatorMixStrategy(IStrategy):
    # region config
    num_of_buy_conditions = 3
    num_of_sell_conditions = 9

    n_buy_conditions_per_group = 0
    n_sell_conditions_per_group = 3
    # endregion
    # region Parameters
    if load:
        im = IndicatorMix()
        im.main()
        buy_comparisons, sell_comparisons = ParameterTools.create_local_parameters(
            im.state,
            locals(),
            num_buy=num_of_buy_conditions,
            num_sell=num_of_sell_conditions,
            # buy_skip_groups=[1, 2],
        )
    # endregion
    # region Params
    sell_params = {
        "sell_comparison_series_2": "bb_slow__bb_middleband",
        "sell_operator_1": ">",
        "sell_operator_2": ">=",
        "sell_series_1": "stoch_sma__stoch_sma",
        "sell_series_2": "t3__T3Average",
    }
    minimal_roi = {"0": 0.05, "30": 0.03, "60": 0.01, "100": 0}
    stoploss = -0.10
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
            inf_dfs[indicator.timeframe] = Populator.populate(
                self.im.state, indicator.name, inf_dfs[indicator.timeframe]
            )
        for tf, df in inf_dfs.items():
            dataframe = merge_informative_pair(dataframe, df, self.timeframe, tf)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for indicator in self.im.indicators.values():
            if indicator.informative:
                continue
            dataframe = Populator.populate(self.im.state, indicator.name, dataframe)
        dataframe = self.populate_informative_indicators(dataframe, metadata)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = Conditions.create_conditions(
            self.im.state,
            dataframe=dataframe,
            comparison_parameters=self.buy_comparisons,
            strategy=self,
            bs='buy',
            n_per_group=self.n_buy_conditions_per_group,
        )
        if conditions:
            if self.n_buy_conditions_per_group > 0:
                dataframe.loc[:, 'buy_tag'] = ''
                dataframe = Conditions.label_tags(dataframe, conditions, 'buy_tag')
                # replace empty tags with None
                dataframe['buy_tag'] = dataframe['buy_tag'].replace('', None)
                dataframe.loc[reduce(lambda x, y: x | y, conditions), 'buy'] = 1
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_tag'] = ''
        conditions = Conditions.create_conditions(
            self.im.state,
            dataframe=dataframe,
            comparison_parameters=self.sell_comparisons,
            strategy=self,
            bs='sell',
            n_per_group=self.n_sell_conditions_per_group,
        )

        if conditions:
            # if sell_comparisons_per_group equals 1, then all conditions will have to be true
            # for a sell signal
            if self.n_sell_conditions_per_group > 0:
                dataframe = Conditions.label_tags(dataframe, conditions, 'exit_tag')
                dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
            # if sell_comparisons_per_group does not equal 1, then any group in the conditions
            # can be True to generate a sell signal
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe
