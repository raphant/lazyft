import datetime
import statistics
from abc import ABCMeta, abstractmethod
from collections import UserList
from pathlib import Path
from typing import Optional, Union, Callable, Type

import pandas as pd
from sqlmodel import Session
from sqlmodel.sql.expression import select

from lazyft import logger, paths
from lazyft.database import engine
from lazyft.errors import IdNotFoundError
from lazyft.models import (
    BacktestReport,
    BacktestRepo,
    HyperoptReport,
    HyperoptRepo,
    ReportBase,
)

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


class _RepoExplorer(UserList[Union[BacktestReport, HyperoptReport]], metaclass=ABCMeta):
    def __init__(
        self, file: Path, repo: Union[Type[BacktestRepo], Type[HyperoptRepo]]
    ) -> None:
        super().__init__()
        self._repo = repo
        self._data_file = file
        self.reset()
        self.df = self.dataframe

    @abstractmethod
    def reset(self):
        pass

    def get(self, *id: str):
        """Get the reports by id"""
        return [r for r in self if r.id in id]

    def get_strategy_id_pairs(self):
        # nt = namedtuple('StrategyPair', ['strategy', 'id'])
        pairs = set()
        for r in self:
            pairs.add((r.strategy, r.hyperopt_id))
        return pairs

    def filter(self, func: Callable[[ReportBase], bool]):
        self.data = list(filter(func, self.data))
        return self

    def sort(self, func: Callable[[ReportBase], bool]):
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
        self.data = sorted(
            self.data, key=lambda r: r.performance.ppd, reverse=not reverse
        )
        return self

    def sort_by_score(self, reverse=False):
        self.data = sorted(
            self.data, key=lambda r: r.performance.score, reverse=not reverse
        )
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

    def dataframe(self) -> Optional[pd.DataFrame]:
        failed = []
        frames = []
        for r in self:
            try:
                frames.append(r.df)
            except FileNotFoundError:
                failed.append(r)
                logger.error(
                    'Failed to find backtest_results for: {}',
                    ', '.join([f'"{f.id}"' for f in failed]),
                )
            except Exception as e:
                failed.append(r)
                logger.exception(e)
        if not len(frames):
            return None
        return pd.DataFrame(pd.concat(frames, ignore_index=True))

    def delete(self, index: int):
        with Session(engine) as session:
            report = self.data[index]
            report.delete(session)
            session.delete(report)
            session.commit()

    def delete_all(self):
        with Session(engine) as session:
            for report in self:
                report.delete(session)
                session.delete(report)
            session.commit()

        logger.info('Deleted {} reports from {}', len(self), self._repo.__name__)


class _BacktestRepoExplorer(_RepoExplorer, UserList[BacktestReport]):
    def reset(self):
        with Session(engine) as session:
            statement = select(BacktestReport)
            results = session.exec(statement)
            self.data = results.fetchall()

        return self.sort_by_date()

    @staticmethod
    def get_hashes():
        with Session(engine) as session:
            statement = select(BacktestReport)
            results = session.execute(statement)
            return [r.hash for r in results.all()]

    def get_using_hash(self, hash: str):
        return [r for r in self if r.hash == hash].pop()

    def filter_by_id(self, *ids: str):
        self.data = [r for r in self if r.param_id in ids]
        return self

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
        for report in self:
            df_trades = report.trades
            mask = (df_trades['open_date'] > start_date) & (
                not end_date or df_trades['open_date'] <= end_date
            )
            df_range = df_trades.loc[mask]
            if not len(df_range):
                continue
            totals_dict = dict(
                strategy=report.strategy,
                id=report.report_id,
                h_id=report.param_id,
                starting_balance=report.balance_info['starting_balance'],
                stake_amount=report.balance_info['stake_amount'],
                # total_profit=df_range.profit_abs.sum(),
                # profit_per_trade=df_range.profit_abs.mean(),
                avg_profit_pct=df_range.profit_ratio.mean() * 100,
                trade_profit_density=df_range.profit_ratio.sum(),
                trades=len(df_range),
                losses=len(df_range[df_range.profit_abs < 0]),
            )
            data.append(totals_dict)
        return pd.DataFrame(data)

    def get_pair_totals(self, sort_by='profit_sum_pct'):
        temp = {}
        for record in self.data:
            df = record.pair_performance
            paired = df[['key', 'profit_sum', 'profit_mean', 'trades']]
            pair_data = paired.to_dict(orient='records')
            for r in pair_data:
                pair = r['key']
                existing_key: dict = temp.get(
                    pair, {'profit_sum_pct': 0, 'mean_collection': [], 'trades': 0}
                )
                current_sum = existing_key['profit_sum_pct']
                trades = existing_key['trades']
                current_mean_collection = existing_key['mean_collection']
                current_sum += r['profit_sum']
                trades += r['trades']
                current_mean_collection.append(r['profit_mean'])
                temp[pair] = {
                    'profit_sum_pct': current_sum,
                    'mean_collection': current_mean_collection,
                    'trades': trades,
                }
        del temp['TOTAL']

        for k, v in temp.copy().items():
            temp[k]['mean'] = statistics.mean(v['mean_collection'])
            del temp[k]['mean_collection']

        df = pd.DataFrame(temp).T
        df['trades'] = df['trades'].astype(int)
        return df.sort_values(sort_by, ascending=False)


class _HyperoptRepoExplorer(_RepoExplorer, UserList[HyperoptReport]):
    def reset(self):
        with Session(engine) as session:
            statement = select(HyperoptReport)
            results = session.exec(statement)
            self.data = results.fetchall()

        return self.sort_by_date()

    def get_by_param_id(self, id: str):
        """Get the report with the uuid or the first report in the repo"""

        try:
            return [r for r in self if str(r.id) == str(id)][0]
        except IndexError:
            raise IdNotFoundError('Could not find report with id %s' % id)

    def get_by_param_ids(self, *ids: str):
        """Get the report with the uuid or the first report in the repo"""
        self.data = [r for r in self if r.param_id in ids]
        return self

    def sort_by_loss(self, reverse=False):
        self.data = sorted(
            self.data,
            key=lambda r: r.performance.loss,
            reverse=reverse,
        )
        return self


def get_backtest_repo():
    return _BacktestRepoExplorer(paths.BACKTEST_RESULTS_FILE, BacktestRepo).reset()


def get_hyperopt_repo():
    return _HyperoptRepoExplorer(paths.PARAMS_FILE, HyperoptRepo).reset()


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


if __name__ == '__main__':
    # print(get_backtest_repo().get_pair_totals('mean').head(15))
    print(get_backtest_repo()[0].backtest_data.keys())
    print(get_backtest_repo()[0].backtest_data['results_per_pair'][-1])
    print(get_backtest_repo().delete_all())
