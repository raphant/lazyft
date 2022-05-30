import logging
from functools import reduce

from freqtrade.strategy.parameters import BaseParameter
from pandas import DataFrame

from indicatormix import condition_tools, populator
from indicatormix.advanced_optimizer import AdvancedOptimizer
from indicatormix.strategy import IMBaseStrategy

logger = logging.getLogger(__name__)


class IMBaseAdvancedOptimizerStrategy(IMBaseStrategy):
    ao: AdvancedOptimizer

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.state = self.ao.state
        self.state.strategy = self
        self.populate_func = populator.populate_with_ranges

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "buy_tag"] = ""
        local_parameters = {
            k: v
            for k, v in self.__class__.__dict__.items()
            if isinstance(v, BaseParameter)
        }
        conditions = self.ao.create_conditions(
            dataframe, local_parameters, "buy", self.n_buy_conditions_per_group
        )
        if conditions:
            if self.n_buy_conditions_per_group > 0:
                dataframe = condition_tools.label_tags(
                    dataframe, conditions, "buy_tag", self.n_buy_conditions_per_group
                )
                # replace empty tags with None
                dataframe.loc[reduce(lambda x, y: x | y, conditions), "buy"] = 1
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), "buy"] = 1
        dataframe["buy_tag"] = dataframe["buy_tag"].replace("", None)
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_tag"] = ""
        local_parameters = {
            k: v
            for k, v in self.__class__.__dict__.items()
            if isinstance(v, BaseParameter)
        }
        conditions = self.ao.create_conditions(
            dataframe, local_parameters, "sell", self.n_sell_conditions_per_group
        )

        if conditions:
            if self.n_sell_conditions_per_group > 0:
                dataframe = condition_tools.label_tags(
                    dataframe, conditions, "exit_tag", self.n_sell_conditions_per_group
                )
                dataframe.loc[reduce(lambda x, y: x | y, conditions), "sell"] = 1
            # if sell_comparisons_per_group does not equal 1, then any group in the conditions
            # can be True to generate a sell signal
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), "sell"] = 1
        return dataframe
