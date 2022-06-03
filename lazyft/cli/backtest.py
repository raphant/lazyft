from enum import Enum

import pandas as pd
import typer
from colorama import Fore

from lazyft import print, strategy
from lazyft.command_parameters import BacktestParameters
from lazyft.reports import get_backtest_repo

app = typer.Typer()


class PerformanceType(str, Enum):
    MONTHLY = "M"
    DAILY = "D"
    WEEKLY = "W"


@app.command("from-hyperopt")
def get_backtests_with_hid(h_id: int = typer.Argument(..., help="Hyperopt ID")):
    """
    Get all backtests for a given hyperopt ID

    :param h_id: int = typer.Argument(..., help="Hyperopt ID")
    :type h_id: int
    """
    reports = get_backtest_repo().filter(lambda x: x.hyperopt_id == str(h_id))
    print(reports.df().to_markdown(), width=1000)


@app.command()
def show(
    id: int,
    type: PerformanceType = typer.Option(None, "-t", "--type", help="Type of performance to show"),
):
    """
    Show backtest performance details.
    """
    report = get_backtest_repo().get(id)
    if not type:
        print(report.report_text)
        return
    print(f"Showing performance for backtest: {report.strategy} with ID: {id}")
    trades: pd.DataFrame = report.trades
    """
    Trades' columns:
    'pair', 'stake_amount', 'amount', 'open_date', 'close_date',
       'open_rate', 'close_rate', 'fee_open', 'fee_close', 'trade_duration',
       'profit_ratio', 'profit_abs', 'sell_reason', 'initial_stop_loss_abs',
       'initial_stop_loss_ratio', 'stop_loss_abs', 'stop_loss_ratio',
       'min_rate', 'max_rate', 'is_open', 'buy_tag', 'open_timestamp',
       'close_timestamp'
    """
    # set index to close_date
    trades.set_index("close_date", inplace=True)
    # add count column
    trades["count"] = 1
    aggregate = {
        "profit_abs": "sum",
        "profit_ratio": "mean",
        "trade_duration": "mean",
        "count": "sum",
    }
    # calculate performance
    if type.value not in ["M", "D", "W"]:
        raise ValueError(f"Invalid performance type: {type}")
    trades = trades.resample(type.value).agg(aggregate)
    # add totals row. Sum profit_abs and average profit_ratio
    trades.loc["Totals"] = trades.agg(aggregate)
    # multiple profit_ratio by 100 to get percentage
    trades["profit_ratio"] = trades["profit_ratio"] * 100
    # print performance
    print(trades.to_markdown())


@app.command()
def run(
    strategy_name: str = typer.Argument(..., help="Strategy name"),
    config: str = typer.Argument(..., help="Config file"),
    interval: str = typer.Argument(..., help="Timeframe interval"),
    days: int = typer.Option(
        None, "-d", "--days", help="Optional number of days. Actual number of days = Days / (1/3)"
    ),
    hyperopt_id: int = typer.Option(
        None, "-h", "--hyperopt-id", help="Hyperopt ID to use for backtest"
    ),
    timerange: str = typer.Option(
        None, "--timerange", help="Time range to use for backtest: YYYYMMDD-YYYYMMDD"
    ),
    max_open_trades: int = typer.Option(
        3, "--mot", "--max-open-trades", help="Maximum number of open trades"
    ),
    stake_amount: float = typer.Option(
        -1, "--sa", "--stake-amount", help="Stake amount in base currency. -1 for unlimited."
    ),
    starting_balance: float = typer.Option(
        100, "-b", "--starting-balance", help="Starting balance in base currency"
    ),
    timeframe_detail: str = typer.Option(
        None, "--td", "--timeframe-detail", help="Timeframe detail"
    ),
    tag: str = typer.Option(None, "--tag", help="Tag"),
    extra_args: str = typer.Option(
        None,
        "-e",
        "--extra-args",
        help="Extra arguments to pass to 'freqtrade backtesting'.\nExample: -e '--enable-protections --eps'",
    ),
):
    """
    Backtest a strategy.

    --days or --timerange is required.
    """
    if strategy_name not in strategy.get_all_strategies():
        typer.echo(Fore.RED + f'Strategy "{strategy_name}" not found.')
        raise typer.Exit(1)
    if not (timerange or days):
        typer.echo(Fore.RED + "--days or --timerange is required.")
        raise typer.Exit(1)
    if stake_amount == -1:
        stake_amount = "unlimited"
    b_params = BacktestParameters(
        timerange=timerange,
        interval=interval,
        config_path=config,
        days=days,
        stake_amount=stake_amount,
        timeframe_detail=timeframe_detail,
        starting_balance=starting_balance,
        max_open_trades=max_open_trades,
        download_data=True,
        tag=tag,
        extra_args=extra_args,
    )
    runner = b_params.run(f'{strategy_name}-{hyperopt_id or ""}', load_from_hash=True)
    runner.save()


@app.command()
def export_trades(
    backtest_id: int = typer.Argument(..., help="Backtest ID"),
    file_name: str = typer.Option(None, "-f", "--file-name", help="File name to export to"),
):
    """
    Export trades to a csv file in the ./exports directory.
    """
    try:
        get_backtest_repo().get(backtest_id).trades_to_csv(file_name)
    except Exception as e:
        print(f"Error exporting trades: {e}")


#
# @app.command()
# def graph(b_id: int = typer.Argument(..., help="Backtest ID")):
#     get_backtest_repo().get(b_id).plot()
