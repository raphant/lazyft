from __future__ import annotations

import logging
import re

import pandas as pd
from lazyft.models import HyperoptReport
from lazyft.reports import get_hyperopt_repo
from pandas import json_normalize

from indicatormix import constants
from indicatormix.constants import OPERATION, SERIES1, SERIES2
from indicatormix.util import string_to_timedelta

logger = logging.getLogger(__name__)


def filter_trial_results(
    report: HyperoptReport,
    buy_or_sell: str,
    min_trades=20,
    min_mean_profit=0.8,
    maximum_duration=5,
    min_profit_total=10,
    min_win_ratio=1,
):
    """
    Returns a list of (epoch, result) pairs from a HyperoptReport object.

    :param report: A HyperoptReport object.
    :param buy_or_sell: Either 'buy' or 'sell'.
    :param min_trades: The minimum number of trades to consider.
    :param min_mean_profit: The minimum mean profit to consider.
    :param maximum_duration: The maximum duration to consider in hours.
    :param min_profit_total: The minimum total profit percent to consider.
    :param min_win_ratio: The minimum win ratio to consider.
    :return: A list of (epoch, result) pairs.
    """
    results = []
    key = 'results_per_buy_tag' if buy_or_sell == 'buy' else 'sell_reason_summary'

    for epoch, trial in enumerate(report.all_epochs):
        df = json_normalize(trial['results_metrics'][key], max_level=1)
        column_name = 'key' if buy_or_sell == 'buy' else 'sell_reason'
        wl_ratio = (
            100.0 / (df['wins'] + df['draws'] + df['losses']) * df['wins']
            if df['losses'].ne(0).any()
            else 100
        )
        df.loc[:, 'win_ratio'] = wl_ratio
        df = df.loc[df[column_name].str.contains('group')]
        for idx, row in df.iterrows():
            delta = string_to_timedelta(row['duration_avg'])
            if (
                # row['win_ratio'] > min_ratio
                row['trades'] >= min_trades
                # and row['profit_total_abs'] > min_profit
                and row['profit_mean_pct'] >= min_mean_profit
                and row['profit_total_pct'] >= min_profit_total
                and row['win_ratio'] >= min_win_ratio
                # duration is under 5 hours
                and delta.total_seconds() < maximum_duration * 60 * 60
            ):
                results.append((epoch, row))
    return results


def print_trial_results(results: list[tuple[int, pd.Series]], buy_or_sell: str):
    """
    Prints the results of a trial.

    :param results: A list of (epoch, result) pairs.
    :param buy_or_sell: Either 'buy' or 'sell'.
    """
    column = 'key' if buy_or_sell == 'buy' else 'sell_reason'
    for epoch, row in results:
        print(
            'Epoch',
            epoch,
            row[column],
            'has a mean profit pct of',
            round(row['profit_mean_pct'], 2),
            'with',
            row['trades'],
            'trades and a profit % of',
            row['profit_total_pct'],
            'with an average duration of',
            row['duration_avg'],
        )


def get_id_group_pairs_from_results(results: list[tuple[int, pd.Series]], buy_or_sell: str):
    """
    Returns a list of (id, group) pairs from a list of (epoch, result) pairs.

    :param results: A list of (epoch, result) pairs.
    """
    column = 'key' if buy_or_sell == 'buy' else 'sell_reason'
    id_group_pairs = []
    for epoch, row in results:
        # row[column] is a string like 'group_123'
        # we only want the numbers
        id_group_pairs.append((epoch, row[column].split('_')[1].strip()))
    return id_group_pairs


def get_parameters_from_id(
    report: HyperoptReport, id_group_pairs: list[tuple[int, str]], buy_or_sell: str
) -> dict:
    """
    Given a list of (id, group) pairs, return a list of parameters for each trial.

    :param report: A HyperoptReport object.
    :param id_group_pairs: A list of (id, group) pairs.
    Some examples would be: (50, '123'), (100, '4567')
    :param buy_or_sell: Either 'buy' or 'sell'.
    :return: A dict of parameters for each trial.
    """
    parameters = {}
    i = 1
    for id, groups in id_group_pairs:
        report.epoch = id
        params = report.parameters
        # for each group in groups, there is a corresponding buy_series, a buy_operator, and a buy_comparison_series.
        # Such as: if groups = '123', then buy_series_1, buy_operator_1, buy_comparison_series_1,
        # buy_series_2, buy_operator_2, buy_comparison_series_2, etc.
        # We want to get each of these and put them in a dictionary and replace the group number with i.
        for n in groups:
            parameters[f'{buy_or_sell}_{constants.SERIES1}_{i}'] = params['params'][buy_or_sell][
                f'{buy_or_sell}_{constants.SERIES1}_{n}'
            ]
            parameters[f'{buy_or_sell}_{constants.OPERATION}_{i}'] = params['params'][buy_or_sell][
                f'{buy_or_sell}_{constants.OPERATION}_{n}'
            ]
            parameters[f'{buy_or_sell}_{constants.SERIES2}_{i}'] = params['params'][buy_or_sell][
                f'{buy_or_sell}_{constants.SERIES2}_{n}'
            ]
            i += 1
    return parameters


def format_parameters(hyperopt_id: int) -> tuple[list, ...]:
    """
    Formats the parameters into {series} {op} {comparison_series} format.

    :param hyperopt_id: The hyperopt id.
    :return: A list of strings. Example: ['vwap__vwap <= sma__SMA', 'sma__SMA <= ema__EMA']
    """
    report = get_hyperopt_repo().get(hyperopt_id)
    parameters = report.parameters['params']
    formatted_parameters = []
    # split unique into groups of n_per_group
    for bs in ['buy', 'sell']:
        temp_parameters = []
        try:
            unique = {int(key.split("_")[-1]) for key in parameters[bs].keys()}
        except ValueError as e:
            raise ValueError(
                f'Some parameters did not have a number at the end in strategy "{report.strategy}". '
                f'Are you sure this is an IndicatorMix strategy?'
            ) from e
        for i in range(min(unique), max(unique) + 1):
            temp_parameters.append(
                f'{parameters[bs][f"{bs}_{SERIES1}_{i}"]} '
                f'{parameters[bs][f"{bs}_{OPERATION}_{i}"]} '
                f'{parameters[bs][f"{bs}_{SERIES2}_{i}"]}'
            )
        formatted_parameters.append(temp_parameters)
    return tuple(formatted_parameters)


def reverse_format_parameters(parameters: list[str], buy_or_sell: str) -> dict:
    """
    Undoes the result of format_parameters.

    :param parameters: A list of strings.
    :param buy_or_sell: Either 'buy' or 'sell'.
    :return: A dictionary of comparisons.
    """
    formatted_parameters = {}
    for i, param in enumerate(parameters):
        formatted_parameters[f'{buy_or_sell}_series_{i + 1}'] = param.split()[0]
        formatted_parameters[f'{buy_or_sell}_operator_{i + 1}'] = param.split()[1]
        formatted_parameters[f'{buy_or_sell}_comparison_series_{i + 1}'] = param.split()[2]
    return formatted_parameters


def timeframe_to_minutes(timeframe: str) -> int:
    """
    Get the timeframe in minutes.
    1d = 1440
    4h = 240
    :return: int
    """

    # timeframe can be: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
    # hours
    try:
        if re.search(r'h', timeframe):
            return int(re.sub(r'h', '', timeframe)) * 60
        # days
        if re.search(r'd', timeframe):
            return int(re.sub(r'd', '', timeframe)) * 1440
        # minute
        return int(re.sub(r'm', '', timeframe))
    except TypeError as e:
        raise ValueError(f'{timeframe} is not a valid timeframe.') from e


def is_bigger_timeframe(timeframe: str, other_timeframe: str) -> bool:
    """
    Returns True if `timeframe` is bigger than `other_timeframe`.

    :param timeframe: A timeframe string.
    :param other_timeframe: A timeframe string.
    """
    return timeframe_to_minutes(timeframe) > timeframe_to_minutes(other_timeframe)


if __name__ == '__main__':
    print(*format_parameters(49))
    # from lazyft.util import get_last_hyperopt_file_path
    #
    # h_file = get_last_hyperopt_file_path()
    # epoch = 1
    # report = HyperoptReport(epoch=epoch, hyperopt_file_str=str(h_file), exchange='kucoin')
    # results = filter_trial_results(report, 'buy', 1, 0.1)
    # from_results = get_id_group_pairs_from_results(results, 'buy')
    # print(from_results)
    # parameters = get_parameters_from_id(report, from_results, 'buy')
    # print(parameters)
    # print(results)

    # sell_params_normal = {
    #     # group1
    #     "sell_series_1": "ema_slow_30m__EMA",
    #     "sell_series_2": "bb_fast_30m__bb_upperband",
    #     "sell_series_3": "ema_fast__EMA",
    #     "sell_operator_1": "<=",
    #     "sell_operator_2": ">",
    #     "sell_operator_3": ">=",
    #     "sell_comparison_series_1": "ema_slow__EMA",
    #     "sell_comparison_series_2": "bb_fast__bb_lowerband",
    #     "sell_comparison_series_3": "open",
    #     # group2
    #     "sell_series_4": "supertrend_fast__supertrend",
    #     "sell_series_5": "bb_fast_1h__bb_middleband",
    #     "sell_series_6": "bb_slow_1h__bb_lowerband",
    #     "sell_operator_4": "<",
    #     "sell_operator_5": "crossed_below",
    #     "sell_operator_6": "<=",
    #     "sell_comparison_series_4": "bb_fast_1h__bb_middleband",
    #     "sell_comparison_series_5": "vwap__vwap",
    #     "sell_comparison_series_6": "hema_fast_1h__hma",
    # }
    # print(format_parameters())
