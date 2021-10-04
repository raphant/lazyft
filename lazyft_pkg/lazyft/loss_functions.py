from datetime import datetime

import numpy as np
from pandas import DataFrame


def win_ratio_and_profit_ratio_loss(
    results: DataFrame,
    trade_count: int,
    min_date: datetime,
    max_date: datetime,
    *args,
    **kwargs
) -> float:
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


def roi_and_profit_hyperopt_loss(
    results: DataFrame, trade_count: int, *args, **kwargs
) -> float:
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
    trailing_stop_loss_signals_rate = (
        results['trailing_stop_loss_signals'].sum() / trade_count
    )

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


def sortino_hyperopt_loss(
    results: DataFrame, trade_count: int, days: int, *args, **kwargs
) -> float:
    """
    Objective function, returns smaller number for more optimal results.

    Uses Sortino Ratio calculation.
    """
    total_profit = results["profit_ratio"]
    days_period = days

    # adding slippage of 0.1% per trade
    total_profit = total_profit - 0.0005
    expected_returns_mean = total_profit.sum() / days_period

    results['downside_returns'] = 0
    results.loc[total_profit < 0, 'downside_returns'] = results['profit_ratio']
    down_stdev = np.std(results['downside_returns'])

    if down_stdev != 0:
        sortino_ratio = expected_returns_mean / down_stdev * np.sqrt(365)
    else:
        # Define high (negative) sortino ratio to be clear that this is NOT optimal.
        sortino_ratio = -20.0

    # print(expected_returns_mean, down_stdev, sortino_ratio)
    return -sortino_ratio
