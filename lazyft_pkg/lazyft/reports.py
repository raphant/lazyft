from abc import ABCMeta, abstractmethod
from collections import UserList
from pathlib import Path
from pprint import pprint
from typing import Optional, Union, Callable, Type

import pandas as pd
import rapidjson
from dateutil.parser import parse

from lazyft import logger
from lazyft.models import (
    BacktestReport,
    BacktestRepo,
    HyperoptReport,
    HyperoptRepo,
    Report,
)
from lazyft.paths import (
    PARAMS_FILE,
    BACKTEST_RESULTS_FILE,
    STRATEGY_DIR,
    PARAMS_DIR,
)
from lazyft.strategy import Strategy


class Parameter:
    @classmethod
    def set_params_file(cls, strategy: str, id: str):
        logger.debug('Copying id file {}.json to strategy folder', id)
        """Load strategy parameters from a saved param export."""
        id_param_file = cls.get_path_of_params(id)
        if not id_param_file.exists():
            raise FileNotFoundError('Could not find parameters for id "%s"' % id)
        # get full name that the params file will be saved as
        strategy_json = Strategy.create_strategy_params_filepath(strategy)
        # setup the file path
        new_params_file = STRATEGY_DIR.joinpath(strategy_json)
        # write into the new params file
        new_params_file.write_text(id_param_file.read_text())
        logger.debug('Finished copying {} -> {}', id_param_file, new_params_file)

    @classmethod
    def get_path_of_params(cls, id):
        """Returns the path to the params file in the saved_params directory using the id"""
        logger.debug('Getting path of params file for id {}', id)
        id_param_file = PARAMS_DIR.joinpath(id + '.json')
        return id_param_file

    @classmethod
    def reset_id(cls, strategy):
        Strategy.create_strategy_params_filepath(strategy).unlink(missing_ok=True)

    @classmethod
    def load_data(cls):
        if not PARAMS_FILE.exists():
            data = {}
        else:
            data = rapidjson.loads(PARAMS_FILE.read_text())
        return data


def get_ppd(r):
    if r.performance.profit == 0:
        return 0
    ppd = (
        r.performance.profit / (r.performance.end_date - r.performance.start_date).days
    )
    return ppd


class RepoExplorer(UserList[Union[BacktestReport, HyperoptReport]], metaclass=ABCMeta):
    def __init__(
        self, file: Path, repo: Union[Type[BacktestRepo], Type[HyperoptRepo]]
    ) -> None:
        super().__init__()
        self._repo = repo
        self._data_file = file
        self.reset()

    def reset(self):
        try:
            self.data = self._repo.parse_file(self._data_file).reports
        except FileNotFoundError:
            logger.error('"{}" not found', self._data_file)

        return self

    def get(self, uuid: str):
        """Get the report with the uuid or the first report in the repo"""
        if uuid:
            return [r for r in self if r.report_id == hash][0]
        return self.data[0]

    def filter(self, func: Callable[[Report], bool]):
        self.data = list(filter(func, self.data))
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

    def sort_by_profit_per_day(self, reverse=False):
        self.data = sorted(self.data, key=lambda r: get_ppd(r), reverse=not reverse)
        return self

    def filter_by_tags(self, *tags: str):
        matched = []
        for r in self:
            if any(set(tags) & set(r.tags)):
                matched.append(r)
        self.data = matched
        return self

    def filter_by_profitable(self):
        self.data = [r for r in self if r.performance.profit > 0]

    def filter_by_id(self, id: str):
        self.data = [r for r in self if r.id == id]
        return self

    def filter_by_strategy(self, strategy: str):
        self.data = [r for r in self if r.strategy == strategy]
        return self

    def filter_by_exchange(self, exchange: str):
        self.data = [r for r in self if r.exchange == exchange]
        return self

    def dataframe(self) -> Optional[pd.DataFrame]:
        if not any(self):
            return None
        data = []
        for r in self:
            d = dict(
                strategy=r.strategy,
                date=r.date,
                id=r.id,
                exchange=r.exchange,
                **r.balance_info.dict(),
                ppd=get_ppd(r),
                **r.performance.dict(),
                days=(r.performance.end_date - r.performance.start_date).days
            )
            data.append(d)
        df = pd.DataFrame(data)
        df.strategy = df.strategy.apply(
            lambda x: ''.join([st for st in x if (st.isupper() | st.isdigit())])
        )
        return df


class BacktestRepoExplorer(RepoExplorer, UserList[BacktestReport]):
    def get_hashes(self):
        return [s.hash for s in self]

    def get_using_hash(self, hash: str):
        return [r for r in self if r.hash == hash].pop()


BacktestRepoExplorer = BacktestRepoExplorer(BACKTEST_RESULTS_FILE, BacktestRepo)
HyperoptRepoExplorer = RepoExplorer(PARAMS_FILE, HyperoptRepo)

if __name__ == '__main__':
    pprint(BacktestRepoExplorer.dataframe())

    # print('Ln70qa:')
    # pprint(ResultBrowser().get_params('BollingerBands2', 'Ln70qa'))
    # print('c32vVv:')
    # pprint(ResultBrowser().get_params('BollingerBands2', 'c32vVv'))
