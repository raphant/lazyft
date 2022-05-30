import math
from datetime import datetime

import numpy as np
from pandas import DataFrame, date_range


def win_ratio_and_profit_ratio_loss(results: DataFrame, trade_count: int) -> float:
    """
    Custom objective function, returns smaller number for better results

    This function optimizes for both: best profit AND stability

    On stability, the final score has an incentive, through 'win_ratio',
    to make more winning deals out of all deals done

    This might prove to be more reliable for dry and live runs of FreqTrade
    and prevent over-fitting on best profit only
    """

    wins = len(results[results['profit_ratio'] > 0])
    avg_profit = results['profit_ratio'].sum() * 100.0

    win_ratio = wins / trade_count
    return -avg_profit * win_ratio * 100


def roi_and_profit_hyperopt_loss(results: DataFrame, trade_count: int) -> float:
    ROI_WEIGHT = 3
    STRATEGY_SELL_WEIGHT = 0
    TRAILING_WEIGHT = 0
    WIN_WEIGHT = 1
    MIN_STOP_LOSS_WEIGHT = 0
    PROFIT_WEIGHT = 20

    SUM_WEIGHT = (
        ROI_WEIGHT
        + STRATEGY_SELL_WEIGHT
        + TRAILING_WEIGHT
        + WIN_WEIGHT
        + MIN_STOP_LOSS_WEIGHT
        + PROFIT_WEIGHT
    )
    # Calculate the rate for different sell reason types
    results.loc[(results['sell_reason'] == 'roi'), 'roi_signals'] = 1
    roi_signals_rate = results['roi_signals'].sum() / trade_count

    results.loc[(results['sell_reason'] == 'sell_signal'), 'strategy_sell_signals'] = 1
    strategy_sell_signal_rate = results['strategy_sell_signals'].sum() / trade_count

    results.loc[
        (results['sell_reason'] == 'trailing_stop_loss'),
        'trailing_stop_loss_signals',
    ] = 1
    trailing_stop_loss_signals_rate = results['trailing_stop_loss_signals'].sum() / trade_count

    results.loc[(results['sell_reason'] == 'stop_loss'), 'stop_loss_signals'] = 1
    stop_loss_signals_rate = results['stop_loss_signals'].sum() / trade_count

    results.loc[(results['profit_ratio'] > 0), 'wins'] = 1
    win_rate = results['wins'].sum() / trade_count

    average_profit = results['profit_ratio'].mean() * 100

    return (
        -1
        * (
            roi_signals_rate * ROI_WEIGHT
            + strategy_sell_signal_rate * STRATEGY_SELL_WEIGHT
            + trailing_stop_loss_signals_rate * TRAILING_WEIGHT
            + win_rate * WIN_WEIGHT
            + (1 - stop_loss_signals_rate) * MIN_STOP_LOSS_WEIGHT
            + average_profit * PROFIT_WEIGHT
        )
        / SUM_WEIGHT
    )


def sharpe_hyperopt_loss(
    results: DataFrame,
    trade_count: int,
    days: int,
):
    """
    Objective function, returns smaller number for more optimal results.

    Uses Sharpe Ratio calculation.
    """
    total_profit = results["profit_ratio"]
    days_period = days

    # adding slippage of 0.1% per trade
    total_profit = total_profit - 0.0005
    expected_returns_mean = total_profit.sum() / days_period
    up_stdev = np.std(total_profit)

    if up_stdev != 0:
        sharp_ratio = expected_returns_mean / up_stdev * np.sqrt(365)
    else:
        # Define high (negative) sharpe ratio to be clear that this is NOT optimal.
        sharp_ratio = -20.0

    # print(expected_returns_mean, up_stdev, sharp_ratio)
    return -sharp_ratio


def sortino_daily(results: DataFrame, trade_count: int, *args, **kwargs) -> float:
    """
    Objective function, returns smaller number for more optimal results.

    Uses Sortino Ratio calculation.

    Sortino Ratio calculated as described in
    http://www.redrockcapital.com/Sortino__A__Sharper__Ratio_Red_Rock_Capital.pdf
    """
    min_date = results.close_date.min()
    max_date = results.close_date.max()
    resample_freq = '1D'
    slippage_per_trade_ratio = 0.0005
    days_in_year = 365
    minimum_acceptable_return = 0.0

    # apply slippage per trade to profit_ratio
    results.loc[:, 'profit_ratio_after_slippage'] = (
        results['profit_ratio'] - slippage_per_trade_ratio
    )

    # create the index within the min_date and end max_date
    t_index = date_range(start=min_date, end=max_date, freq=resample_freq, normalize=True)

    sum_daily = (
        results.resample(resample_freq, on='close_date')
        .agg({"profit_ratio_after_slippage": sum})
        .reindex(t_index)
        .fillna(0)
    )

    total_profit = sum_daily["profit_ratio_after_slippage"] - minimum_acceptable_return
    expected_returns_mean = total_profit.mean()

    sum_daily['downside_returns'] = 0
    sum_daily.loc[total_profit < 0, 'downside_returns'] = total_profit
    total_downside = sum_daily['downside_returns']
    # Here total_downside contains min(0, P - MAR) values,
    # where P = sum_daily["profit_ratio_after_slippage"]
    down_stdev = math.sqrt((total_downside ** 2).sum() / len(total_downside))

    if down_stdev != 0:
        sortino_ratio = expected_returns_mean / down_stdev * math.sqrt(days_in_year)
    else:
        # Define high (negative) sortino ratio to be clear that this is NOT optimal.
        sortino_ratio = -20.0

    # print(t_index, sum_daily, total_profit)
    # print(minimum_acceptable_return, expected_returns_mean, down_stdev, sortino_ratio)
    return sortino_ratio
