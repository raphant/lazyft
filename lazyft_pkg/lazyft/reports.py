import datetime
from abc import ABCMeta, abstractmethod
from collections import UserList
from functools import reduce
from itertools import combinations
from pprint import pprint
from typing import Union, Callable, Any

import pandas as pd
from dateutil.parser import parse
from freqtrade.optimize.optimize_reports import (
    text_table_bt_results,
    text_table_tags,
    text_table_sell_reason,
    generate_periodic_breakdown_stats,
    text_table_periodic_breakdown,
    text_table_add_metrics,
)
from sqlmodel import Session
from sqlmodel.sql.expression import select
import re
from lazyft import logger
from lazyft.database import engine
from lazyft.errors import IdNotFoundError
from lazyft.models import (
    BacktestReport,
    HyperoptReport,
    ReportBase,
)
from lazyft.notify import notify_telegram
from lazyft.util import dict_to_telegram_string

cols_to_print = [
    'strategy',
    'h_id',
    'date',
    'exchange',
    'starting_balance',
    'max_open_trades',
    'tpd',
    'trades',
    'days',
    'tag',
]
BacktestReportList = UserList[BacktestReport]
HyperoptReportList = UserList[HyperoptReport]
RepoList = Union[UserList[BacktestReport], UserList[HyperoptReport]]
AbstractReport = Union[BacktestReport, HyperoptReport]


class _RepoExplorer(UserList[AbstractReport], metaclass=ABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.df = self.dataframe

    @abstractmethod
    def reset(self) -> '_RepoExplorer':
        pass

    def get(self, id: int) -> AbstractReport:
        """Gets a report by id"""
        try:
            return [r for r in self if str(r.id) == str(id)][0]
        except IndexError:
            raise IdNotFoundError('Could not find report with id %s' % id)

    def get_strategy_id_pairs(self):
        # nt = namedtuple('StrategyPair', ['strategy', 'id'])
        pairs = set()
        for r in self:
            pairs.add((r.strategy, r.hyperopt_id))
        return pairs

    def filter(self, func: Callable[[ReportBase], bool]):
        self.data = list(filter(func, self.data))
        return self

    def sort(self, func: Callable[[ReportBase], bool]) -> '_RepoExplorer':
        self.data = sorted(self.data, key=func, reverse=True)
        return self

    def head(self, n: int):
        self.data = self.data[:n]
        return self

    def tail(self, n: int):
        self.data = self.data[-n:]
        return self

    def sort_by_date(self, reverse=False):
        self.data = sorted(self.data, key=lambda r: r.date, reverse=not reverse)
        return self

    def sort_by_profit(self, reverse=False):
        self.data = sorted(
            self.data,
            key=lambda r: r.performance.profit,
            reverse=not reverse,
        )
        return self

    def sort_by_ppd(self, reverse=False):
        self.data = sorted(self.data, key=lambda r: r.performance.ppd, reverse=not reverse)
        return self

    def sort_by_score(self, reverse=False):
        self.data = sorted(self.data, key=lambda r: r.performance.score, reverse=not reverse)
        return self

    def filter_by_id(self, *ids: str):
        self.data = [r for r in self if r.id in ids]
        return self

    def filter_by_tag(self, *tags: str):
        matched = []
        for r in self:
            if r.tag in tags:
                matched.append(r)
        self.data = matched
        return self

    def filter_by_profitable(self):
        self.data = [r for r in self if r.performance.profit > 0]
        return self

    def filter_by_strategy(self, *strategies: str):
        self.data = [r for r in self if r.strategy in strategies]
        return self

    def filter_by_exchange(self, exchange: str):
        self.data = [r for r in self if r.exchange == exchange]
        return self

    def first(self):
        return self.data[0]

    def last(self):
        return self.data[-1]

    def dataframe(self) -> pd.DataFrame:
        frames = []
        for r in self:
            try:
                frames.append(r.df)
            except Exception as e:
                logger.exception('Failed to create dataframe for report: %s', r)
                logger.debug(e)
        if not len(frames):
            logger.info('No dataframes created')
            return pd.DataFrame()
        frame = pd.DataFrame(pd.concat(frames, ignore_index=True))
        frame.set_index('id', inplace=True)
        frame.loc[frame.stake == -1.0, 'stake'] = 'unlimited'
        frame['avg_profit_pct'] = frame['avg_profit_pct'] * 100
        frame.sort_values(by='id', ascending=False, inplace=True)
        return frame

    def delete(self, *id: int):
        """Delete the reports by id"""
        reports = self.filter_by_id(*id)
        with Session(engine) as session:
            for report in reports:
                report.delete(session)
                session.delete(report)
                logger.info('Deleted report id: {}', report.id)
            session.commit()

    def delete_all(self):
        with Session(engine) as session:
            for report in self:
                report.delete(session)
                session.delete(report)
            session.commit()

        logger.info('Deleted {} reports from {}', len(self), self.__class__.__name__)


class _BacktestRepoExplorer(_RepoExplorer, BacktestReportList):
    def reset(self) -> '_BacktestRepoExplorer':
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
            .sort_values('td', ascending=False)
            .drop_duplicates(subset=['strategy'])
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
            mask = (df_trades['open_date'].dt.date > start_date) & (
                not end_date or df_trades['open_date'].dt.date <= end_date
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
        return pd.DataFrame(data).set_index('id')

    def get_pair_totals(self, sort_by='profit_total_pct'):
        """Get trades from all saved reports and summarize them."""
        all_trades = pd.concat([r.trades for r in self])
        df = all_trades.groupby(all_trades['pair']).aggregate(
            profit_total=pd.NamedAgg(column='profit_abs', aggfunc='sum'),
            profit_total_pct=pd.NamedAgg(column='profit_ratio', aggfunc='sum'),
            profit_pct=pd.NamedAgg(column='profit_ratio', aggfunc='mean'),
            avg_stake_amount=pd.NamedAgg(column='stake_amount', aggfunc='mean'),
            count=pd.NamedAgg(column='pair', aggfunc='count'),
        )
        df.profit_total_pct = df.profit_total_pct * 100
        df.profit_pct = df.profit_pct * 100
        return df.sort_values(sort_by, ascending=False)


class _HyperoptRepoExplorer(_RepoExplorer, HyperoptReportList):
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
            raise IdNotFoundError('Could not find report with id %s' % id)

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
    return _BacktestRepoExplorer().reset()


def get_hyperopt_repo():
    return _HyperoptRepoExplorer().reset()


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
    results: dict[str, Any],
    stake_currency: str,
    backtest_breakdown=None,
    hyperopt=False,
) -> str:
    """
    Generate a text report from a backtest results dict.
    """
    text = []
    if backtest_breakdown is None:
        backtest_breakdown = []
    # Print results
    text.append(f"Result for strategy {strategy} | Hyperopt: {hyperopt}")
    table = text_table_bt_results(results['results_per_pair'], stake_currency=stake_currency)
    if isinstance(table, str):
        text.append(' BACKTESTING REPORT '.center(len(table.splitlines()[0]), '='))
    text.append(table)

    if results.get('results_per_buy_tag') is not None:
        table = text_table_tags(
            "buy_tag", results['results_per_buy_tag'], stake_currency=stake_currency
        )

        if isinstance(table, str) and len(table) > 0:
            text.append(' BUY TAG STATS '.center(len(table.splitlines()[0]), '='))
        text.append(table)

    table = text_table_sell_reason(
        sell_reason_stats=results['sell_reason_summary'], stake_currency=stake_currency
    )
    if isinstance(table, str) and len(table) > 0:
        text.append(' SELL REASON STATS '.center(len(table.splitlines()[0]), '='))
    text.append(table)

    table = text_table_bt_results(results['left_open_trades'], stake_currency=stake_currency)
    if isinstance(table, str) and len(table) > 0:
        text.append(' LEFT OPEN TRADES REPORT '.center(len(table.splitlines()[0]), '='))
    text.append(table)

    for period in backtest_breakdown:
        days_breakdown_stats = generate_periodic_breakdown_stats(
            trade_list=results['trades'], period=period
        )
        table = text_table_periodic_breakdown(
            days_breakdown_stats=days_breakdown_stats, stake_currency=stake_currency, period=period
        )
        if isinstance(table, str) and len(table) > 0:
            text.append(f' {period.upper()} BREAKDOWN '.center(len(table.splitlines()[0]), '='))
        text.append(table)

    table = text_table_add_metrics(results)
    if isinstance(table, str) and len(table) > 0:
        text.append(' SUMMARY METRICS '.center(len(table.splitlines()[0]), '='))
    text.append(table)

    if isinstance(table, str) and len(table) > 0:
        text.append('=' * len(table.splitlines()[0]))

    text.append('')
    return '\n'.join(text)


if __name__ == '__main__':
    # print(get_backtest_repo().get_pair_totals('mean').head(15))
    # print(get_hyperopt_repo())
    # print(get_backtest_repo())
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
    print(get_hyperopt_repo().get(38).hyperopt_list_to_df().to_markdown())
    # print(get_hyperopt_repo().get(38).performance.profit_total_pct * 100)
    # print(get_backtest_repo().head(20).df().to_markdown())
    # print(get_backtest_repo().get(275).report_text)
    # notify_telegram('Test', dict_to_telegram_string(get_hyperopt_repo().get(38).performance.dict()))
    report = get_hyperopt_repo().get(38)

    def find_epochs_that_meet_requirement(report: HyperoptReport):
        minimum_profit_pct = 0.03
        maximum_drawdown = 0.4
        minimum_win_rate = 0.5
        df = report.hyperopt_list_to_df()
        print(df.keys())
        profit_key = 'Profit'
        drawdown_key = 'max_drawdown_account'
        wins_draw_loss_key = 'Win Draw Loss'

        def split_wins_draws_losses(row):
            wdl_val = row[wins_draw_loss_key]  # Example: 79    0   75
            pattern = re.compile(r'(\d+)\s+(\d+)\s+(\d+)')
            wins, draws, losses = pattern.match(wdl_val).groups()
            return wins, draws, losses

        def calculate_win_ratio(wins, draws, losses):
            return (int(wins) + int(draws)) / (int(wins) + int(draws) + int(losses))

        df['win_ratio'] = df.apply(
            lambda row: calculate_win_ratio(*split_wins_draws_losses(row)), axis=1
        )
        print(df['win_ratio'])
        # filter out epochs that don't meet requirements
        meets_req = df.query(
            f'{profit_key} > {minimum_profit_pct} and {drawdown_key} < {maximum_drawdown} and win_ratio > {minimum_win_rate}'
        )
        meets_req = meets_req.sort_values(profit_key, ascending=False)
        print(meets_req[profit_key])
        print(meets_req.head(10))
        reports = []
        for idx, row in meets_req.iterrows():
            new_report = report.new_report_from_epoch(idx)
            reports.append(new_report)
            assert new_report.performance.profit_total_pct == row[profit_key]
        return reports

    # find_epochs_that_meet_requirement(report)
    print(get_backtest_repo().first().performance.profit_total_pct)
    print(get_hyperopt_repo().first().performance.profit_total_pct)
    notify_telegram('Test', dict_to_telegram_string(report.performance.dict()))
