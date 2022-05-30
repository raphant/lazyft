from __future__ import annotations

import logging
from functools import reduce
from itertools import zip_longest

from freqtrade.strategy import IStrategy
from pandas import DataFrame, Series

from indicatormix import State, constants
from indicatormix.custom_exceptions import InvalidComparisonError, InvalidSeriesError
from indicatormix.entities.comparison import create

logger = logging.getLogger(__name__)


def label_tags(
    dataframe: DataFrame, conditions: list[Series], tag_type: str, n_per_group: int
) -> DataFrame:
    for idx, cond in enumerate(conditions, start=1):
        group_start = (idx * n_per_group) - n_per_group + 1
        num_group = list(range(group_start, idx * n_per_group + 1))
        dataframe.loc[cond, tag_type] += f'group_{"".join([str(n) for n in num_group])} '

    return dataframe


def group_conditions(conditions: list[Series], n_per_group: int) -> list[Series]:
    """
    Group conditions into groups of n_per_group conditions.

    :param conditions: List of conditions
    :param n_per_group: Number of conditions per group
    :return: List of conditions
    """
    final: list[Series] = []
    # group conditions by groups of n_per_group
    group = list(zip_longest(*[iter(conditions)] * n_per_group, fillvalue=True))
    # go through each condition group and make compare the individual conditions
    for g in group:
        combined = reduce(lambda x, y: x & y, g)
        final.append(combined)
    return final


def create_conditions(
    state: State,
    dataframe: DataFrame,
    comparison_parameters: dict,
    strategy: IStrategy,
    bs: str,
    n_per_group: int = None,
) -> list[Series]:
    """
    Load the passed conditions for the given dataframe using the comparison parameters.

    :param state: State object that holds all loaded indicators
    :param dataframe: Dataframe to create conditions for
    :param comparison_parameters: Parameters for the comparison generated by hyperopt
    :param strategy: Strategy object used to load the parameters
    :param bs: 'buy' or 'sell'
    :param n_per_group: Number of conditions per group
    :return: List of conditions
    """
    should_group_conditions = n_per_group > 0
    conditions = []
    for comparison_no in comparison_parameters:
        series1 = getattr(strategy, f'{bs}_{constants.SERIES1}_{comparison_no}').value
        op = getattr(strategy, f'{bs}_{constants.OPERATION}_{comparison_no}').value
        comparison_series = getattr(strategy, f'{bs}_{constants.SERIES2}_{comparison_no}').value
        # continue if series1 or op is None
        if series1 == 'none':
            continue
        try:
            comparison = create(state, series1, op, comparison_series)
            logger.debug('Created comparison %s', comparison)
        except (InvalidSeriesError, InvalidComparisonError) as e:
            logger.debug(f'Could not create comparison "{series1} {op} {comparison_series}": {e}')
            continue
        try:
            compare_result = comparison.compare(state, dataframe, bs)
            # check if any value in the compare_result Series is None
            if compare_result.isnull().all():
                raise InvalidComparisonError(
                    f'All values are null in {series1} {op} {comparison_series}'
                )
            conditions.append(compare_result)
        except InvalidComparisonError as e:
            logger.debug(f'Could not execute comparison: {e}')
            continue
        except Exception as e:
            logger.error('Error comparing %s, %s, %s', series1, op, comparison_series)
            raise e

    return group_conditions(conditions, n_per_group) if should_group_conditions else conditions
