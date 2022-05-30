from enum import Enum
from pprint import pprint

import typer
from lazyft.reports import get_hyperopt_repo

app = typer.Typer()


class SortBy(str, Enum):
    profit = "profit"
    avg_profit = "avg_profit"
    trades = "trades"


@app.command()
def show(
    id: int, show_params: bool = typer.Option(False, '--params', '-p', help="Show parameters")
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


@app.command('list')
def list_(
    strategy: str = typer.Option(None, '-s', '--strategy', help="Filter by strategy"),
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
