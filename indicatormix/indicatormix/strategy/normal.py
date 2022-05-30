import logging
from functools import reduce

from pandas import DataFrame

from indicatormix import condition_tools, populator
from indicatormix.custom_exceptions import InvalidComparisonError
from indicatormix.entities.comparison import Comparison
from indicatormix.main import IndicatorMix
from indicatormix.strategy import IMBaseStrategy

logger = logging.getLogger(__name__)


class IMBaseNormalOptimizationStrategy(IMBaseStrategy):
    """
    Where IMS parameters are tested.
    """

    im: IndicatorMix
    buy_comparisons: dict[str, Comparison]
    sell_comparisons: dict[str, Comparison]

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.state = self.im.state
        self.state.strategy = self
        self.populate_func = populator.populate

        # get all BaseParameter instances in locals()
        # if __name__ == __qualname__:
        #     parameters = [
        #         param
        #         for name, param in self.__class__.__dict__.items()
        #         if isinstance(param, BaseParameter) and 'buy' in name
        #     ]
        #     for parameter in parameters:
        #         if parameter.optimize or parameter.value != 'none':
        #             break
        #     else:
        #         raise BuyParametersEmpty(
        #             f'No buy parameters are optimizable. Please check your strategy.\n'
        #             f'Buy parameters: {parameters}'
        #         )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        The function takes in a dataframe and a dictionary with the pair to populate.
        It then loops through each indicator and populates the dataframe with the indicator's name.
        It then calls the populate_informative_indicators function.

        :param dataframe: The dataframe to be populated
        :type dataframe: DataFrame
        :param metadata: dict
        :type metadata: dict
        :return: The dataframe with all the indicators populated.
        """
        for indicator in self.state.indicators.values():
            if indicator.informative:
                continue
            dataframe = populator.populate(self.state, indicator.name, dataframe)
        dataframe = self.populate_informative_indicators(dataframe, metadata)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        It creates a buy_tag column and populates it with the conditions.

        :param dataframe: The dataframe to be populated
        :type dataframe: DataFrame
        :param metadata: dict
        :type metadata: dict
        :return: A dataframe with a buy column and a buy_tag column.
        """
        dataframe.loc[:, 'buy_tag'] = ''

        conditions = condition_tools.create_conditions(
            self.state,
            dataframe=dataframe,
            comparison_parameters=self.buy_comparisons,
            strategy=self,
            bs='buy',
            n_per_group=self.n_buy_conditions_per_group,
        )
        if conditions:
            try:
                if self.n_buy_conditions_per_group > 0:
                    dataframe = condition_tools.label_tags(
                        dataframe, conditions, 'buy_tag', self.n_buy_conditions_per_group
                    )
                    # replace empty tags with None
                    dataframe.loc[reduce(lambda x, y: x | y, conditions), 'buy'] = 1
                else:
                    dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
            except Exception as e:
                raise InvalidComparisonError(
                    f'Fail to populate buy_trend: {self.buy_comparisons}.\n'
                    f'Head: {conditions[:5]}\nTail: {conditions[-5:]}'
                ) from e
        dataframe.loc[:, 'buy_tag'] = dataframe['buy_tag'].replace('', None)
        dataframe.loc[dataframe['volume'] == 0, 'buy'] = 0
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        The function takes in a dataframe and a dictionary with the pair.
        It then creates a list of conditions based on the pair.
        It then creates a list of tags based on the conditions.
        It then adds the tags to the dataframe.
        It then adds a sell signal to the dataframe based on the tags.

        :param dataframe: The dataframe to be used for the condition generation
        :type dataframe: DataFrame
        :param metadata: dict
        :type metadata: dict
        :return: A dataframe with a sell column and an exit_tag column.
        """
        dataframe.loc[:, 'exit_tag'] = ''
        conditions = condition_tools.create_conditions(
            self.state,
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
