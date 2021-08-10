from abc import ABCMeta, abstractmethod
from collections import UserList
from pathlib import Path
from pprint import pprint
from typing import Optional, Union, Callable

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


class RepoExplorer(UserList[Union[BacktestReport, HyperoptReport]], metaclass=ABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self.reset()

    @abstractmethod
    def reset(self):
        pass

    def filter(self, func: Callable[[Report], bool]):
        self.data = list(filter(func, self.data))
        return self

    def head(self, n: int):
        self.data = self.data[:n]

    def tail(self, n: int):
        self.data = self.data[-n:]

    def sort_by_date(self, reverse=False):
        self.data = sorted(self.data, key=lambda r: r.date, reverse=reverse)
        return self

    def sort_by_profit(self, reverse=False):
        self.data = sorted(
            self.data,
            key=lambda r: r.performance.profit,
            reverse=not reverse,
        )
        return self

    def sort_by_profit_per_day(self, reverse=False):
        def get_ppd(r):
            if r.performance.profit == 0:
                return 0
            ppd = (
                r.performance.profit
                / (r.performance.end_date - r.performance.start_date).days
            )
            return ppd

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
    def reset(self):
        try:
            reports = BacktestRepo.parse_file(BACKTEST_RESULTS_FILE).reports
        except FileNotFoundError:
            pass
        else:
            self.extend(reports)
        return self

    def get_hashes(self):
        return [s.hash for s in self]

    def get_using_hash(self, hash: str):
        return [r for r in self if r.hash == hash].pop()


class HyperoptRepoExplorer(RepoExplorer, UserList[HyperoptReport]):
    def reset(self):
        try:
            reports = HyperoptRepo.parse_file(PARAMS_FILE).reports
        except FileNotFoundError:
            pass
        else:
            self.extend(reports)
        return self

    def by_profitable(self):
        self.data = [r for r in self if r.performance.tot_profit > 0]


class BacktestReportBrowser:
    @classmethod
    def data(cls):
        if not BACKTEST_RESULTS_FILE.exists():
            return {}
        return rapidjson.loads(BACKTEST_RESULTS_FILE.read_text())

    @classmethod
    def get_hashes(cls, strategy: str):
        return [p.get('hash') for p in cls.data().get(strategy, {})]

    @classmethod
    def get_backtest_results(cls, strategy: str):
        if strategy not in cls.data():
            raise KeyError(
                'Strategy "%s" not found in %s' % (strategy, BACKTEST_RESULTS_FILE.name)
            )
        performances = []
        for p in cls.data()[strategy]:
            data = {'id': p.get('id'), 'exchange': p.get('exchange')}
            data.update(p['performance'])
            data.update(
                {
                    'start_date': p.get('start_date'),
                    'end_date': p.get('end_date'),
                }
            )
            performances.append(data)
        df = pd.DataFrame(performances)
        return df

    @classmethod
    def get_all_backtest_results(cls):
        frames = []
        for s in cls.data():
            df = cls.get_backtest_results(s)
            df.insert(2, 'strategy', s)
            df.strategy = df.strategy.apply(
                lambda x: ''.join([st for st in x if (st.isupper() | st.isdigit())])
            )
            frames.append(df)
        return pd.concat(frames)

    @classmethod
    def get_backtest_result_from_id(cls, strategy: str, id: str):
        if strategy not in cls.data() or id not in [strategy]:
            raise KeyError(
                'Strategy "%s" or id "%s" not found in %s'
                % (strategy, id, BACKTEST_RESULTS_FILE.name)
            )
        data = [cls.data()[strategy][id]['performance']]
        return pd.DataFrame(data)

    @classmethod
    def get_backtest_by_hash(cls, strategy: str, hash: str) -> Optional[dict]:
        for p in cls.data()[strategy]:
            if p.get('hash') == hash:
                return p


class HyperoptReportsBrowser:
    @classmethod
    def data(cls):
        if not PARAMS_FILE.exists():
            return {}
        return rapidjson.loads(PARAMS_FILE.read_text())

    @classmethod
    def get_performances(cls, strategy: str) -> pd.DataFrame:
        performances = []
        assert strategy in cls.data(), "Strategy doesn't exist"
        for id, id_dict in cls.data()[strategy].items():
            perf = {'id': id, 'exchange': id_dict.get('exchange')}
            perf.update(id_dict.get('balance_info', {}))
            perf.update(id_dict['performance'])
            perf['days'] = abs(parse(perf['from_date']) - parse(perf['to_date'])).days
            perf.pop('to_date')
            performances.append(perf)

        df = pd.DataFrame(performances)
        return df

    @classmethod
    def get_params(cls, strategy: str, id: str):
        try:
            return rapidjson.loads(
                Path(cls.data()[strategy][id]['params_file']).read_text()
            )
        except KeyError:
            raise KeyError('Could not load params for %s-%s' % (strategy, id))


if __name__ == '__main__':
    report_filter = BacktestRepoExplorer()
    pprint(report_filter.dataframe())

    # print('Ln70qa:')
    # pprint(ResultBrowser().get_params('BollingerBands2', 'Ln70qa'))
    # print('c32vVv:')
    # pprint(ResultBrowser().get_params('BollingerBands2', 'c32vVv'))
