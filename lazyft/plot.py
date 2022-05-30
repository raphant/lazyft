from typing import Sequence

import pandas as pd
import plotly.express as px

from lazyft.reports import get_hyperopt_repo, get_backtest_repo


def calculate_equity(strategy_stats: dict) -> list:
    """
    Get the equity curve for a strategy.

    :param strategy_stats: Strategy stats dictionary.
    :return: pd.Series with the equity curve.
    """
    profits = []
    for date_profit in strategy_stats['daily_profit']:
        profits.append(date_profit[1])
    equity = 0
    equity_daily = []
    for daily_profit in profits:
        equity_daily.append(equity)
        equity += float(daily_profit)
    return equity_daily


def get_dates_from_strategy(strategy_stats: dict) -> list:
    """
    Get the dates for a strategy.

    :param strategy_stats: Strategy stats dictionary.
    :return: pd.Series with the dates.
    """
    dates = []
    for date_profit in strategy_stats['daily_profit']:
        dates.append(date_profit[0])
    return dates


def get_dataframe_with_equity_series(report_ids: Sequence[int], type_: str) -> pd.DataFrame:
    """
    Get the equity curve for a list of strategies.

    :param report_ids: List of strategy ids to get the equity curve for.
    :param type_: 'backtest' or 'hyperopt'.
    :return: pd.DataFrame with the equity curve.
    """
    repo = get_backtest_repo() if type_ == 'backtest' else get_hyperopt_repo()
    # set column "date" to dates of first series
    strategy_stats = repo.get(report_ids[0]).backtest_data
    df = pd.DataFrame({"date": get_dates_from_strategy(strategy_stats)})
    # add all equity series to dataframe
    for report_id in report_ids:
        strategy_stats = repo.get(report_id).backtest_data
        df.loc[:, f'equity_daily_{report_id}'] = calculate_equity(strategy_stats)
    return df


def plot_equity_curves(*report_ids: int, type='hyperopt') -> None:
    """
    Plot the equity curves for a list of strategies.
    :param report_ids: List of strategy ids to get the equity curve for.
    :param type: 'backtest' or 'hyperopt'.
    :return: None
    """
    if len(report_ids) == 1:
        get_backtest_repo().get(report_ids[0]).plot()
        return
    df = get_dataframe_with_equity_series(report_ids, type)
    # get all column names with "equity_daily" in it
    cols = [col for col in df.columns if "equity_daily" in col]
    fig = px.line(df, x="date", y=cols, title="Equity Curve")
    fig.show()


if __name__ == '__main__':
    # plot equity curves for strategies: 92 and 93
    plot_equity_curves(90, 91, 92, 93)
