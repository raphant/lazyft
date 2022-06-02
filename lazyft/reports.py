import datetime
import re
from abc import ABCMeta, abstractmethod
from collections import UserList
from typing import Any, Callable, Generic, Iterable, TypeVar, Union

import pandas as pd
from dateutil.parser import parse
from freqtrade.optimize.optimize_reports import (
    generate_periodic_breakdown_stats,
    text_table_add_metrics,
    text_table_bt_results,
    text_table_exit_reason,
    text_table_periodic_breakdown,
    text_table_tags,
)
from sqlmodel import Session
from sqlmodel.sql.expression import select

from lazyft import logger
from lazyft.database import engine
from lazyft.errors import IdNotFoundError
from lazyft.models.backtest import BacktestReport
from lazyft.models.hyperopt import HyperoptReport

cols_to_print = [
    "strategy",
    "h_id",
    "date",
    "exchange",
    "starting_balance",
    "max_open_trades",
    "tpd",
    "trades",
    "days",
    "tag",
]
BacktestReportList = UserList[BacktestReport]
HyperoptReportList = UserList[HyperoptReport]
RepoList = Union[UserList[BacktestReport], UserList[HyperoptReport]]
AbstractReport = Union[BacktestReport, HyperoptReport]

T = TypeVar("T")


class RepoExplorer(UserList[T], metaclass=ABCMeta):
    """
    A database API used to query, sort, filter, and delete reports.
    """

    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.df = self.dataframe

    @abstractmethod
    def reset(self) -> "RepoExplorer":
        """
        Queries the database and returns a list of all reports

        :return: RepoExplorer with all reports.
        :rtype: RepoExplorer
        """
        pass

    def get(self, id: int) -> T:
        """
        Returns the report with the given id.

        :param id: The id of the report to return.
        :type id: int
        :raises IdNotFoundError: If no report with the given id is found.
        :return: The report with the given id.
        :rtype: ReportBase
        """
        try:
            return [r for r in self if str(r.id) == str(id)][0]
        except IndexError:
            raise IdNotFoundError("Could not find report with id %s" % id)

    def get_strategy_id_pairs(self) -> Iterable[tuple[str, int]]:
        """
        Returns an iterable of tuples of strategy names and ids.


        :return: An iterable of tuples of strategy names and ids.
        :rtype: Iterable[tuple[str, int]]
        """
        pairs = set()
        for r in self:
            pairs.add((r.strategy, r.hyperopt_id))
        return pairs

    def filter(self, func: Callable[[T], bool]) -> U:
        """
        Filters the list of reports using a function.

        :param func: The function to use to filter the list.
        :type func: Callable[[ReportBase], bool]
        :return: RepoExplorer with the filtered reports.
        :rtype: RepoExplorer
        """
        self.data = list(filter(func, self.data))
        return self

    # noinspection PyMethodOverriding
    def sort(self, func: Callable[[T], bool]) -> "RepoExplorer":
        """
        Sorts the list of reports using a function.

        :param func: The function to use to sort the list.
        :type func: Callable[[ReportBase], bool]
        :return: RepoExplorer with the sorted reports.
        :rtype: RepoExplorer
        """
        self.data = sorted(self.data, key=func, reverse=True)
        return self

    def head(self, n: int) -> "RepoExplorer":
        """
        Returns the first n reports.

        :param n: The number of reports to return.
        :type n: int
        :return: RepoExplorer with the first n reports.
        :rtype: RepoExplorer
        """
        self.data = self.data[:n]
        return self

    def tail(self, n: int) -> "RepoExplorer":
        """
        Returns the last n reports.

        :param n: The number of reports to return.
        :type n: int
        :return: RepoExplorer with the last n reports.
        :rtype: RepoExplorer
        """
        self.data = self.data[-n:]
        return self

    def sort_by_date(self, ascending=False) -> "RepoExplorer":
        """
        Sorts the list of reports by date.

        :param ascending: Sort in lowest to highest date order, defaults to False
        :type ascending: bool, optional
        :return: RepoExplorer with the sorted reports.
        :rtype: RepoExplorer
        """
        self.data = sorted(self.data, key=lambda r: r.date, reverse=not ascending)
        return self

    def sort_by_profit(self, ascended=False) -> "RepoExplorer":
        """
        Sorts the list of reports by profit.

        :param ascended: Sort in lowest to highest profit order, defaults to False
        :type ascended: bool, optional
        :return: RepoExplorer with the sorted reports.
        :rtype: RepoExplorer
        """
        self.data = sorted(
            self.data,
            key=lambda r: r.performance.profit_percent,
            reverse=not ascended,
        )
        return self

    def sort_by_ppd(self, ascended=False) -> "RepoExplorer":
        """
        Sorts the list of reports by profit per day.

        :param ascended: Sort in lowest to highest profit per day order, defaults to False
        :type ascended: bool, optional
        :return: RepoExplorer with the sorted reports.
        :rtype: RepoExplorer
        """
        self.data = sorted(
            self.data, key=lambda r: r.performance.ppd, reverse=not ascended
        )
        return self

    def sort_by_score(self, ascending=False) -> "RepoExplorer":
        """
        Sorts the list of reports by score.


        :param ascending: Sort in lowest to highest score order, defaults to False
        :type ascending: bool, optional
        :return: RepoExplorer with the sorted reports.
        :rtype: RepoExplorer
        """
        self.data = sorted(
            self.data, key=lambda r: r.performance.score, reverse=not ascending
        )
        return self

    def filter_by_id(self, ids: Iterable[int]) -> "RepoExplorer":
        """
        Filters the list of reports by ids.

        :param ids: The ids to filter by.
        :type ids: Iterable[int]
        :return: RepoExplorer with the filtered reports.
        :rtype: RepoExplorer
        """
        self.data = [r for r in self if r.id in ids]
        return self

    def filter_by_tag(self, tags: Iterable[str]) -> "RepoExplorer":
        """
        Filters the list of reports by tags.

        :param tags: The tags to filter by.
        :type tags: Iterable[str]
        :return: RepoExplorer with the filtered reports.
        :rtype: RepoExplorer
        """
        matched = []
        for r in self:
            if r.tag in tags:
                matched.append(r)
        self.data = matched
        return self

    def filter_by_profitable(self) -> "RepoExplorer":
        """
        Filters the list of reports by profitability.

        :return: RepoExplorer with the filtered reports.
        :rtype: RepoExplorer
        """
        self.data = [r for r in self if r.performance.profit > 0]
        return self

    def filter_by_strategy(self, strategies: Iterable[str]) -> "RepoExplorer":
        """
        Filters the list of reports by strategies.

        :param strategies: The strategies to filter by.
        :type strategies: Iterable[str]
        :return: RepoExplorer with the filtered reports.
        :rtype: RepoExplorer
        """
        new_data = []
        for r in self:
            try:
                if r.strategy in strategies:
                    new_data.append(r)
            except IndexError as e:
                logger.warning(
                    f"Could not find strategy {r.strategy} in {strategies}: {e}"
                )
                continue
        self.data = new_data
        return self

    def filter_by_exchange(self, exchange: str) -> "RepoExplorer":
        """
        Filters the list of reports by exchanges.

        :param exchange: The exchange to filter by.
        :type exchange: str
        :return: RepoExplorer with the filtered reports.
        :rtype: RepoExplorer
        """
        self.data = [r for r in self if r.exchange == exchange]
        return self

    def first(self) -> T:
        """
        Returns the first report.

        :return: The first report.
        :rtype: ReportBase
        """
        return self.data[0]

    def last(self) -> T:
        """
        Returns the last report.

        :return: The last report.
        :rtype: ReportBase
        """
        return self.data[-1]

    def dataframe(self) -> pd.DataFrame:
        """
        Returns a dataframe of the reports.

        :return: A dataframe of the reports.
        :rtype: pd.DataFrame
        """
        frames = []
        for r in self:
            try:
                frames.append(r.df)
            except Exception as e:
                logger.exception("Failed to create dataframe for report: %s", r)
                logger.debug(e)
        if not len(frames):
            print("No dataframes created")
            return pd.DataFrame()
        frame = pd.DataFrame(pd.concat(frames, ignore_index=True))
        frame.set_index("id", inplace=True)
        frame.loc[frame.stake == -1.0, "stake"] = "unlimited"
        frame["avg_profit_pct"] = frame["avg_profit_pct"] * 100
        frame.sort_values(by="id", ascending=False, inplace=True)
        return frame

    def delete(self, ids: Iterable[int]) -> None:
        """
        Deletes reports by ids.

        :param ids: The ids to delete.
        :type ids: Iterable[int]
        :return: RepoExplorer with the deleted reports.
        :rtype: RepoExplorer
        """
        reports = self.filter_by_id(*ids)
        with Session(engine) as session:
            for report in reports:
                report.delete(session)
                session.delete(report)
                logger.info("Deleted report id: {}", report.id)
            session.commit()

    def delete_all(self) -> None:
        """
        Deletes all reports.
        """
        with Session(engine) as session:
            for report in self:
                report.delete(session)
                session.delete(report)
            session.commit()

        logger.info("Deleted {} reports from {}", len(self), self.__class__.__name__)

    def length(self) -> int:
        """
        Returns the length of the list of reports.

        :return: The number of reports in the database.
        :rtype: int
        """
        return len(self)


class BacktestRepoExplorer(RepoExplorer[BacktestReport], BacktestReportList):
    def reset(self) -> "BacktestRepoExplorer":
        with Session(engine) as session:
            statement = select(BacktestReport)
            results = session.exec(statement)
            self.data = results.fetchall()

        return self.sort_by_date()

    @staticmethod
    def get_hashes():
        with Session(engine) as session:
            statement = select(BacktestReport)
            results = session.exec(statement)
            return [r.hash for r in results.all()]

    def get_using_hash(self, hash: str):
        return [r for r in self if r.hash == hash].pop()

    def get_top_strategies(self, n=3):
        return (
            self.df()
            .sort_values("td", ascending=False)
            .drop_duplicates(subset=["strategy"])
            .head(n)
        )

    def get_results_from_date_range(
        self,
        start_date: Union[datetime.datetime, str],
        end_date: Union[datetime.datetime, str] = None,
    ) -> pd.DataFrame:
        data = []
        if isinstance(start_date, str):
            start_date = parse(start_date).date()
        if isinstance(end_date, str):
            end_date = parse(end_date).date()
        for report in self:
            df_trades = report.trades
            mask = (df_trades["open_date"].dt.date > start_date) & (
                not end_date or df_trades["open_date"].dt.date <= end_date
            )
            df_range = df_trades.loc[mask]
            if not len(df_range):
                continue
            totals_dict = dict(
                strategy=report.strategy,
                id=report.id,
                h_id=report.hyperopt_id,
                starting_balance=report.starting_balance,
                stake_amount=report.stake_amount,
                # total_profit=df_range.profit_abs.sum(),
                # profit_per_trade=df_range.profit_abs.mean(),
                avg_profit_pct=df_range.profit_ratio.mean() * 100,
                total_profit_pct=df_range.profit_ratio.sum(),
                trades=len(df_range),
                wins=len(df_range[df_range.profit_abs > 0]),
                draws=len(df_range[df_range.profit_abs == 0]),
                losses=len(df_range[df_range.profit_abs < 0]),
            )
            data.append(totals_dict)
        return pd.DataFrame(data).set_index("id")

    def get_pair_totals(self, sort_by="profit_total_pct"):
        """Get trades from all saved reports and summarize them."""
        all_trades = pd.concat([r.trades for r in self])
        df = all_trades.groupby(all_trades["pair"]).aggregate(
            profit_total=pd.NamedAgg(column="profit_abs", aggfunc="sum"),
            profit_total_pct=pd.NamedAgg(column="profit_ratio", aggfunc="sum"),
            profit_pct=pd.NamedAgg(column="profit_ratio", aggfunc="mean"),
            avg_stake_amount=pd.NamedAgg(column="stake_amount", aggfunc="mean"),
            count=pd.NamedAgg(column="pair", aggfunc="count"),
        )
        df.profit_total_pct = df.profit_total_pct * 100
        df.profit_pct = df.profit_pct * 100
        return df.sort_values(sort_by, ascending=False)


class HyperoptRepoExplorer(RepoExplorer[HyperoptReport], HyperoptReportList):
    def reset(self):
        with Session(engine) as session:
            statement = select(HyperoptReport)
            results = session.exec(statement)
            self.data = results.fetchall()

        return self.sort(lambda r: r.id)

    def get_by_param_id(self, id: str):
        """Get the report with the uuid or the first report in the repo"""
        try:
            return [r for r in self if str(r.id) == str(id)][0]
        except IndexError:
            raise IdNotFoundError("Could not find report with id %s" % id)

    def get_by_param_ids(self, *ids: str):
        """Get the report with the uuid or the first report in the repo"""
        self.data = [r for r in self if r.id in ids]
        return self

    def sort_by_loss(self, reverse=False):
        self.data = sorted(
            self.data,
            key=lambda r: r.performance.loss,
            reverse=reverse,
        )
        return self


def get_backtest_repo():
    """
    Returns the backtest repo.
    """
    return BacktestRepoExplorer().reset()


def get_hyperopt_repo():
    """
    Returns the hyperopt repo.
    """
    return HyperoptRepoExplorer()


class BacktestExplorer:
    @staticmethod
    def get_hashes():
        with Session(engine) as session:
            statement = select(BacktestReport)
            results = session.exec(statement)
            return [r.hash for r in results.fetchall()]

    @classmethod
    def get_using_hash(cls, hash):
        with Session(engine) as session:
            statement = select(BacktestReport).where(BacktestReport.hash == hash)
            results = session.exec(statement)
            return results.one()


def backtest_results_as_text(
    strategy: str,
    id: int,
    results: dict[str, Any],
    stake_currency: str,
    backtest_breakdown=None,
    hyperopt=False,
    hyperopt_id=None,
) -> str:
    """
    Generate a text report from a backtest results dict.
    Modified FreqTrade code
    """
    text = []
    if backtest_breakdown is None:
        backtest_breakdown = []
    # Print results
    header_str = f"Result for strategy {strategy} #{id} | Hyperopt: {hyperopt}"
    if not hyperopt and hyperopt_id is not None:
        header_str += f" | Hyperopt id: {hyperopt_id}"
    text.append(header_str)
    table = text_table_bt_results(
        results["results_per_pair"], stake_currency=stake_currency
    )
    if isinstance(table, str):
        text.append(" BACKTESTING REPORT ".center(len(table.splitlines()[0]), "="))
    text.append(table)
    text.append("=" * len(table.splitlines()[0]) + "\n")

    if results.get("results_per_enter_tag") is not None:
        table = text_table_tags(
            "enter_tag", results["results_per_enter_tag"], stake_currency=stake_currency
        )

        if isinstance(table, str) and len(table) > 0:
            text.append(" Enter TAG STATS ".center(len(table.splitlines()[0]), "="))
        text.append(table)
        text.append("=" * len(table.splitlines()[0]) + "\n")

    table = text_table_exit_reason(
        exit_reason_stats=results["exit_reason_summary"], stake_currency=stake_currency
    )
    if isinstance(table, str) and len(table) > 0:
        text.append(" Exit REASON STATS ".center(len(table.splitlines()[0]), "="))
        text.append(table)
        text.append("=" * len(table.splitlines()[0]) + "\n")

    table = text_table_bt_results(
        results["left_open_trades"], stake_currency=stake_currency
    )
    if isinstance(table, str) and len(table) > 0:
        text.append(" LEFT OPEN TRADES REPORT ".center(len(table.splitlines()[0]), "="))
        text.append(table)
        text.append("=" * len(table.splitlines()[0]) + "\n")

    for period in backtest_breakdown:
        days_breakdown_stats = generate_periodic_breakdown_stats(
            trade_list=results["trades"], period=period
        )
        table = text_table_periodic_breakdown(
            days_breakdown_stats=days_breakdown_stats,
            stake_currency=stake_currency,
            period=period,
        )
        if isinstance(table, str) and len(table) > 0:
            text.append(
                f" {period.upper()} BREAKDOWN ".center(len(table.splitlines()[0]), "=")
            )
        text.append("=" * len(table.splitlines()[0]))

        text.append(table + "\n")

    table = text_table_add_metrics(results)
    if isinstance(table, str) and len(table) > 0:
        text.append(" SUMMARY METRICS ".center(len(table.splitlines()[0]), "="))
    text.append(table)

    if isinstance(table, str) and len(table) > 0:
        text.append("=" * len(table.splitlines()[0]))

    text.append("")
    return "\n".join(text)


if __name__ == "__main__":
    # print(get_backtest_repo().get_pair_totals('mean').head(15))
    # print(get_hyperopt_repo().filter_by_strategy('ImsPlay'))
    # print(get_backtest_repo())
    print(get_backtest_repo().sort_by_profit().first().strategy_hash)
    # print(get_hyperopt_repo())

    # t1 = time.time()
    # print(get_backtest_repo().head(20).df().to_markdown())
    # first_report = get_backtest_repo().head(1)[0]
    # print(first_report.backtest_data.keys())
    # # print(str(get_hyperopt_repo()))
    #
    # print('Elapsed time:', time.time() - t1, 'seconds')
    # StrategyBackup.first().print()
    # report = get_hyperopt_repo().last()
    # print(report.get_best_epoch(), report.epoch)
    # print(get_hyperopt_repo().get(35).parameters['params']['buy'])
    # print(get_backtest_repo().head(10).df().to_markdown())
    # print(get_hyperopt_repo().get(38).performance.profit_total_pct * 100)
    # print(get_backtest_repo().head(20).df().to_markdown())
    # print(get_backtest_repo().get(275).report_text)
    # notify_telegram('Test', dict_to_telegram_string(get_hyperopt_repo().get(38).performance.dict()))
    # report = get_hyperopt_repo().get(38)

    # def meets_requirements(drawdown, profit_pct, win_rate, is_hyperopt=True):
    #     if is_hyperopt:
    #         maximum_drawdown = 0.4
    #         minimum_profit_pct = 1.0
    #         minimum_win_rate = 0.4
    #     else:
    #         maximum_drawdown = 0.30
    #         minimum_profit_pct = 1.0
    #         minimum_win_rate = 0.4
    #     reason = ''
    #     meets = True
    #     if win_rate < minimum_win_rate:
    #         meets = False
    #         reason = 'win_rate'
    #     if profit_pct < minimum_profit_pct:
    #         meets = False
    #         reason = 'profit_pct'
    #     if drawdown > maximum_drawdown:
    #         meets = False
    #         reason = 'drawdown'
    #     return meets, reason

    # def find_epochs_that_meet_requirement(report: HyperoptReport, n_results: int = 10):
    #     logger.info(f'Searching for epochs that meet requirements for report #{report.id}')
    #     profit_key = 'Profit'
    #     drawdown_key = 'max_drawdown_account'
    #     wins_draw_loss_key = 'Win Draw Loss'
    #     df = report.hyperopt_list_to_df()
    #     # drop duplicates on all columns but the index
    #     new_df = df.drop_duplicates(
    #         subset=df.columns.difference([profit_key, drawdown_key, wins_draw_loss_key]),
    #         keep='first',
    #     )
    #     logger.info(f'Dropped {len(df) - len(new_df)} duplicate epochs from report #{report.id}')
    #     df = new_df
    #
    #     # df = df.drop_duplicates(subset=[wins_draw_loss_key, profit_key, drawdown_key], keep='last')
    #
    #     def split_wins_draws_losses(row):
    #         wdl_val = row[wins_draw_loss_key]  # Example: 79    0   75
    #         pattern = re.compile(r'(\d+)\s+(\d+)\s+(\d+)')
    #         wins, draws, losses = pattern.match(wdl_val).groups()
    #         return wins, draws, losses
    #
    #     df['win_ratio'] = df.apply(
    #         lambda row: calculate_win_ratio(*split_wins_draws_losses(row)), axis=1
    #     )
    #     # filter out epochs that don't meet requirements
    #
    #     # use meets_requirements function to filter out epochs that don't meet requirements
    #     meets_req = df.apply(
    #         lambda row: meets_requirements(
    #             row[drawdown_key], row[profit_key], row['win_ratio'], is_hyperopt=True
    #         )[0],
    #         axis=1,
    #     )
    #     meets_req = df[meets_req]
    #     meets_req = meets_req.sort_values('Objective', ascending=False)
    #     # get the top n best results by profit
    #     meets_req = meets_req.head(n_results)
    #     reports = []
    #     for idx, row in meets_req.iterrows():
    #         new_report = report.new_report_from_epoch(idx)
    #         new_report.save()
    #         reports.append(new_report)
    #         # assert new_report.performance.profit_total_pct == row[profit_key]
    #     return reports

    # print(report.parameters)
    # find_epochs_that_meet_requirement(report)
    # r = get_hyperopt_repo().df()
    # df = r.hyperopt_list_to_df()
    # df.sort_values('Objective', ascending=True).to_markdown()
    # print(get_hyperopt_repo().first().performance.profit_total_pct)
    # notify_telegram('Test', dict_to_telegram_string(report.performance.dict()))
    # report = get_backtest_repo().sort_by_profit().first()
    # print(report.backtest_data['holding_avg'])
    # print(report.df.to_markdown())
