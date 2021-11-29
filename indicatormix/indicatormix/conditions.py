from functools import reduce
from itertools import zip_longest

from freqtrade.strategy import IStrategy
from pandas import DataFrame, Series

from indicatormix import State
from indicatormix.custom_exceptions import InvalidSeriesError
from indicatormix.entities.comparison import create
from indicatormix.main import logger


class Conditions:
    @staticmethod
    def create_conditions(
        state: State,
        dataframe: DataFrame,
        comparison_parameters: dict,
        strategy: IStrategy,
        bs: str,
        n_per_group: int = None,
    ) -> list[Series]:
        """
        Create conditions for each comparison creating in populate_buy/sell_trend
        Args:
            state: State object
            dataframe: DataFrame from populate_buy/sell_trend
            comparison_parameters: dictionary of comparison parameters
            strategy:
            bs:
            n_per_group:

        Returns: list of condition series
        """
        conditions = []
        for n_group in comparison_parameters:
            after_series = getattr(strategy, f'{bs}_series_{n_group}').value
            op = getattr(strategy, f'{bs}_operator_{n_group}').value
            comparison_series = getattr(
                strategy, f'{bs}_comparison_series_{n_group}'
            ).value
            try:
                comparison = create(state, after_series, op, comparison_series)
                logger.info('Created comparison %s', comparison)
            except InvalidSeriesError:
                continue
            try:
                conditions.append(comparison.compare(state, dataframe, bs))
            except Exception as e:
                logger.error(
                    'Error comparing %s, %s, %s', after_series, op, comparison_series
                )
                raise e
            conditions.append((dataframe['volume'] > 0))
        if n_per_group == 0:
            return conditions

        return Conditions.group_conditions(conditions, n_per_group)

    @staticmethod
    def group_conditions(conditions: list[Series], n_per_group: int) -> list[Series]:
        final: list[Series] = []
        # group conditions by groups of n_per_group
        group = zip_longest(*[iter(conditions)] * n_per_group, fillvalue=True)
        # go through each condition group and make compare the individual conditions
        for g in group:
            combined = reduce(lambda x, y: x & y, g)
            final.append(combined)
        return final

    @staticmethod
    def label_tags(dataframe: DataFrame, conditions: list[Series], tag: str):
        for idx, cond in enumerate(conditions, start=1):
            dataframe.loc[cond, tag] = f'group_{idx} '
        # replace empty tags with None
        dataframe[tag] = dataframe[tag].replace('', None)
        return dataframe
