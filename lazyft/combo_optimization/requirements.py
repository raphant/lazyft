"""
requirements.py
"""
import re

from lazyft.combo_optimization import logger
from lazyft.models import BacktestReport, HyperoptReport
from lazyft.util import calculate_win_ratio


def split_wins_draws_losses(row, wins_draw_loss_key: str):
    """
    Given a row of data, split the wins, draws, and losses from the wins_draw_loss_key

    :param row: The row of the dataframe that we're operating on
    :param wins_draw_loss_key: The key in the row that contains the wins/draws/losses value
    :type wins_draw_loss_key: str
    :return: A tuple of three integers.
    """
    wdl_val = row[wins_draw_loss_key]  # Example: 79    0   75
    pattern = re.compile(r"(\d+)\s+(\d+)\s+(\d+)")
    wins, draws, losses = pattern.match(wdl_val).groups()
    return wins, draws, losses


def meets_requirements(drawdown, profit_pct, win_rate, ppt, requirements: dict):
    """
    The function checks if the report meets the requirements.

    :param drawdown: The percentage drop from the highest profit to the lowest
    :param profit_pct: The percentage of the bet amount that you win
    :param win_rate: The win rate of the strategy
    :param ppt: Profit per trade
    :param requirements: The requirements to meet
    :type requirements: dict
    :return: A tuple of the following:
        A boolean indicating whether the strategy meets the requirements
        A list of reasons why the strategy does not meet the requirements
    """
    reasons = []
    try:
        if win_rate < requirements["win_rate"]:
            reasons.append("win_rate")
        elif profit_pct < requirements["profit_pct"]:
            reasons.append("profit_pct")
        elif ppt < requirements["ppt"]:
            reasons.append("ppt")
        elif drawdown > requirements["drawdown"]:
            reasons.append("drawdown")
    except KeyError:
        raise KeyError(
            "The requirements dictionary is missing a required key. "
            "The expected keys are: win_rate, profit_pct, ppt, and drawdown. "
        )

    return not any(reasons), reasons


def report_meets_requirements(report: BacktestReport, requirements: dict):
    """
    The function checks if the report meets the requirements.
    If it does not meet the requirements, it will print out the reason why it does not meet the
    requirement.

    :param report: HyperoptReport
    :type report: HyperoptReport
    :param requirements: The requirements to meet
    :type requirements: dict
    :return: A report object
    """
    meets, reasons = meets_requirements(
        report.drawdown,
        report.performance.profit_total_pct,
        report.performance.win_loss_ratio,
        report.performance.profit_ratio,
        requirements,
    )
    if not meets:
        for reason in reasons:
            if reason == "win_rate":
                logger.info(
                    f"Backtest #{report.id} does not meet win rate requirement ({report.performance.win_loss_ratio})"
                )
            if reason == "profit_pct":
                logger.info(
                    f"Backtest #{report.id} does not meet profit requirement ({report.performance.profit_total_pct})"
                )
            if reason == "drawdown":
                logger.info(
                    f"Backtest #{report.id} does not meet drawdown requirement ({report.performance.drawdown})"
                )
            if reason == "ppt":
                logger.info(
                    f"Backtest #{report.id} does not meet profit per trade requirement ({report.performance.profit_ratio})"
                )
    return meets


def find_epochs_that_meet_requirement(
    report: HyperoptReport, requirements: dict, n_results: int = 10
):
    """
    Given a report, find the epochs that meet the requirements and return the top n epochs by profit

    :param report: The report to search in
    :type report: HyperoptReport
    :param requirements: The requirements to meet
    :type requirements: dict
    :param n_results: int = 10, defaults to 10
    :type n_results: int (optional)
    :return: A list of HyperoptReport objects
    """
    profit_key = "Profit"
    drawdown_key = "max_drawdown_account"
    avg_profit_key = "Avg profit"
    wins_draw_loss_key = "Win Draw Loss"
    df = report.hyperopt_list_to_df()
    logger.info(
        f"Searching {len(df)} epochs for results that meet requirements in report #{report.id}"
    )
    # drop duplicates on all columns but the index
    new_df = df.drop_duplicates(
        subset=df.columns.difference([profit_key, drawdown_key, wins_draw_loss_key]),
        keep="first",
    )
    logger.info(f"Dropped {len(df) - len(new_df)} duplicate epochs from report #{report.id}")
    df = new_df

    # df = df.drop_duplicates(subset=[wins_draw_loss_key, profit_key, drawdown_key], keep='last')

    df["win_ratio"] = df.apply(
        lambda row: calculate_win_ratio(*split_wins_draws_losses(row, wins_draw_loss_key)), axis=1
    )
    # df = df.sort_values('Objective', ascending=True)
    # filter out epochs that don't meet requirements

    # use meets_requirements function to filter out epochs that don't meet requirements
    meets_req = df.apply(
        lambda row: meets_requirements(
            row[drawdown_key],
            row[profit_key],
            row["win_ratio"],
            row[avg_profit_key],
            requirements,
        )[0],
        axis=1,
    )
    meets_req = df[meets_req]
    meets_req = meets_req.sort_values("Objective", ascending=True)
    # get the top n best results by profit
    meets_req = meets_req.head(n_results)
    reports = []
    for idx, row in meets_req.iterrows():
        new_report = report.new_report_from_epoch(idx)
        new_report.save()
        reports.append(new_report)
        # assert new_report.performance.profit_total_pct == row[profit_key]
    return reports


def should_update_hyperopt_baseline(
    current_report: BacktestReport, potential_report: BacktestReport
):
    """
    Check to see if the new performance is better than the current best.
    """
    if not current_report:
        return True
    return (
        # drawdown
        # potential_report.drawdown <= current_report.drawdown and
        # profit
        potential_report.performance.profit_total_pct
        > current_report.performance.profit_total_pct
        # potential_report.performance.win_loss_ratio > current_report.performance.win_loss_ratio
    )
