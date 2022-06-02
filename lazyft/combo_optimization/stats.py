"""
stats.py
"""
import statistics
from typing import TYPE_CHECKING

from lazyft.combo_optimization import notify
from lazyft.models import BacktestReport, HyperoptReport
from lazyft.util import dict_to_telegram_string

if TYPE_CHECKING:
    from lazyft.combo_optimization.combo_optimizer import ComboOptimizer


def append_stats(
    hyperopt_report: HyperoptReport,
    backtest_report: BacktestReport,
    stats: dict[str, list],
):
    """
    Append stats to the stats file.
    """

    stats["backtest_average_profit"].append(backtest_report.performance.profit_total_pct)
    stats["backtest_average_drawdown"].append(backtest_report.performance.drawdown)
    stats["backtest_average_win_rate"].append(backtest_report.performance.win_ratio)
    stats["backtest_average_trades"].append(backtest_report.performance.trades)
    stats["backtest_average_profit_per_trade"].append(backtest_report.performance.profit_ratio)
    stats["hyperopt_average_profit"].append(hyperopt_report.performance.profit_total_pct)
    stats["hyperopt_average_drawdown"].append(hyperopt_report.performance.drawdown)
    stats["hyperopt_average_win_rate"].append(hyperopt_report.performance.win_ratio)
    stats["hyperopt_average_trades"].append(hyperopt_report.performance.trades)
    stats["hyperopt_average_profit_per_trade"].append(hyperopt_report.performance.profit_ratio)


def print_stats(stats: dict[str, list], optimizer: "ComboOptimizer", last_n=20):
    """
    It prints the average stats of the last 20 trials

    :param stats: dict[str, list]
    :type stats: dict[str, list]
    :param optimizer: ComboOptimizer
    :type optimizer: ComboOptimizer
    :param last_n: The number of previous reports to average over, defaults to 20 (optional)
    """
    if optimizer.current_idx % 5 == 0 and len(stats["backtest_average_profit"]) > 1:
        try:
            # get last_n results
            stats = {
                "avg_profit": statistics.mean(stats["hyperopt_average_profit"][-last_n:]),
                "avg_drawdown": statistics.mean(stats["hyperopt_average_drawdown"][-last_n:]),
                "avg_win_rate": statistics.mean(stats["hyperopt_average_win_rate"][-last_n:]),
                "avg_trades": statistics.mean(stats["hyperopt_average_trades"][-last_n:]),
                "avg_profit_per_trade": statistics.mean(
                    stats["hyperopt_average_profit_per_trade"][-last_n:]
                ),
            }
            backtest_stats = {
                "avg_profit": statistics.mean(stats["backtest_average_profit"][-last_n:]),
                "avg_drawdown": statistics.mean(stats["backtest_average_drawdown"][-last_n:]),
                "avg_win_rate": statistics.mean(stats["backtest_average_win_rate"][-last_n:]),
                "avg_trades": statistics.mean(stats["backtest_average_trades"][-last_n:]),
                "avg_profit_per_trade": statistics.mean(
                    stats["backtest_average_profit_per_trade"][-last_n:]
                ),
            }
        except statistics.StatisticsError:
            pass
        else:
            notify(
                f"Checkpoint trial {optimizer.current_trial}-{optimizer.current_idx} - "
                f"{len(optimizer.meets)} report(s) meet requirements\n"
                f'Average Hyperopt stats for `last {len(stats["hyperopt_average_profit"][-last_n:])} report(s)`:\n'
                f"{dict_to_telegram_string(stats)}\n\n"
                f'Average Backtest stats for `last {len(stats["backtest_average_profit_per_trade"][-last_n:])} report(s)`:\n'
                f"{dict_to_telegram_string(backtest_stats)}\n"
                f"Current best report: Hyperopt #{optimizer.best_hyperopt_id} - Backtest #{optimizer.best_backtest_id}"
            )
