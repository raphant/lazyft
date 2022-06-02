from enum import Enum
from pprint import pprint

import attr
import typer
from lazyft.command_parameters import HyperoptParameters
from lazyft.errors import IdNotFoundError
from lazyft.reports import get_backtest_repo, get_hyperopt_repo

app = typer.Typer()


class SortBy(str, Enum):
    profit = "profit"
    avg_profit = "avg_profit"
    trades = "trades"


@app.command()
def show(
    id: int,
    show_params: bool = typer.Option(False, "--params", "-p", help="Show parameters"),
):
    """
    Show hyperopt details.

    :param id: Backtest ID.
    :type id: int
    :param show_params: Show parameters.
    :type show_params: bool
    """
    report = get_hyperopt_repo().get(id)
    print(report.report_text)
    if show_params:
        pprint(report.parameters)


@app.command("list")
def list_(
    strategy: str = typer.Option(None, "-s", "--strategy", help="Filter by strategy"),
    sort_by: SortBy = typer.Option(None, help="How the results should be sorted"),
):
    """List previous hyperopt results."""
    repo = get_hyperopt_repo()
    if strategy:
        repo = repo.filter_by_strategy(strategy)
    if sort_by:
        if sort_by == SortBy.profit:
            repo = repo.sort_by_profit()
        elif sort_by == SortBy.avg_profit:
            repo = repo.sort(lambda x: x.performance.profit_ratio)
        elif sort_by == SortBy.trades:
            repo = repo.sort(lambda x: x.performance.trades)
        else:
            raise ValueError(f"Unknown sort_by: {sort_by}")
    print(repo.df().to_markdown())


@app.command("run")
def run(
    strategy_name: str = typer.Argument(..., help="Strategy name"),
    config: str = typer.Argument(..., help="Config file"),
    interval: str = typer.Argument(..., help="Timeframe interval"),
    days: int = typer.Option(
        None,
        "-d",
        "--days",
        help="Optional number of days. Actual number of days = Days / (1/3)",
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
        -1,
        "--sa",
        "--stake-amount",
        help="Stake amount in base currency. -1 for unlimited.",
    ),
    starting_balance: float = typer.Option(
        100, "-b", "--starting-balance", help="Starting balance in base currency"
    ),
    timeframe_detail: str = typer.Option(
        None, "--td", "--timeframe-detail", help="Timeframe detail"
    ),
    tag: str = typer.Option(None, "--tag", help="Tag"),
):
    raise NotImplementedError()


@app.command("run-on-backtest")
def run_from_backtest(
    backtest_id: int = typer.Argument(..., help="Backtest ID"),
    config: str = typer.Argument(..., help="Config file"),
    epochs: int = typer.Option(100, "-e", "--epochs", help="Number of epochs"),
    spaces: str = typer.Option("default", "-s", "--spaces", help="Space to use"),
    loss_function: str = typer.Option(
        "SortinoHyperOptLoss", "-l", "--loss-function", help="Loss function"
    ),
    min_trades: int = typer.Option(1, "-t", "--min-trades"),
    timerange: str = typer.Option(
        None, "--timerange", help="Time range to use for backtest: YYYYMMDD-YYYYMMDD"
    ),
    auto_save: bool = typer.Option(
        False, "-s", "--auto-save", help="Save results automatically"
    ),
):
    """
    Runs a hyperopt with the same configuration settings from a previous backtest.
    """
    try:
        report = get_backtest_repo().get(backtest_id)
    except IdNotFoundError:
        typer.echo(f"Backtest ID {backtest_id} not found")
        raise typer.Exit(1)
    bp = report.get_backtest_parameters(config=config)
    hp = HyperoptParameters(
        **attr.asdict(bp),
        min_trades=min_trades,
        epochs=epochs,
        spaces=spaces,
        loss=loss_function,
    )
    hp.timerange = timerange or bp.timerange
    try:
        runner = hp.run(report.strategy, autosave=auto_save, verbose=True)
    except Exception as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)

    if not runner.report:
        if not runner.error:
            typer.echo("No results available")
        else:
            typer.echo(f"{runner.err_output}", color=True)
        raise typer.Exit(1)
