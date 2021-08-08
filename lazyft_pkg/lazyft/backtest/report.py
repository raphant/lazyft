import datetime
import pathlib
from collections import defaultdict
from dataclasses import dataclass
from pprint import pprint
from typing import Union

import dateutil.parser as parser
import pandas as pd
import rapidjson

from lazyft import regex, paths
from lazyft.pairlist import Pairlist
from lazyft.paths import BACKTEST_RESULTS_FILE
from lazyft.strategy import Strategy


class BacktestSaver:
    @staticmethod
    def save(performance: 'Performance'):
        data = BacktestSaver.add_to_existing_data(performance)
        BACKTEST_RESULTS_FILE.write_text(rapidjson.dumps(data, indent=2))
        return performance.id

    @staticmethod
    def add_to_existing_data(performance: 'Performance') -> dict:
        # grab all data
        data = defaultdict(list, BacktestSaver.get_existing_data())
        # add the current params to id in strategy data
        data[performance.strategy].append(
            {
                "id": performance.id,
                "performance": performance.total,
                "start_date": performance.start_date,
                "end_date": performance.end_date,
            }
        )
        return data

    @staticmethod
    def get_existing_data() -> dict:
        if BACKTEST_RESULTS_FILE.exists():
            return rapidjson.loads(BACKTEST_RESULTS_FILE.read_text())
        return {}


class BacktestReport:
    def __init__(
        self, strategy: str, min_win_rate: float, json_file: Union[str], id: str = None
    ) -> None:
        self.strategy = strategy
        self.min_win_rate = min_win_rate
        self.json_file = pathlib.Path(
            paths.USER_DATA_DIR, 'backtest_results', json_file
        ).resolve()
        self._json_data = None
        self.id = id

    def save(self):
        to_dict = self.totals.to_dict(orient='records')[0]
        to_dict.pop('key')
        start_date = self.json_data['strategy'][self.strategy]['backtest_start']
        end_date = self.json_data['strategy'][self.strategy]['backtest_end']
        performance = Performance(to_dict, self.id, self.strategy, start_date, end_date)
        return BacktestSaver.save(performance)

    def add_super_earners_to_whitelist(self, pct: float):
        Strategy.add_pairs_to_whitelist(self.strategy, *list(self.get_winners(pct).key))

    def add_super_losers_to_blacklist(self, pct: float):
        Strategy.add_pairs_to_blacklist(self.strategy, *list(self.get_losers(pct).key))

    def get_losers(self, pct: float):
        df = self.df.loc[self.df['profit_total_pct'] < pct].copy()
        df = df[df.key != 'TOTAL']
        return df

    def get_winners(self, pct: float):
        df = self.df.loc[self.df['profit_total_pct'] > pct].copy()
        df = df[df.key != 'TOTAL']
        return df

    @property
    def trades(self):
        return pd.DataFrame(self._json_data['strategy'][self.strategy]['trades'])

    @property
    def totals(self):
        tail = self.df.tail(1)
        key = f'{self.strategy}'
        if self.id:
            key = key + f'-{self.id}'
        tail.key = key
        return tail

    @property
    def total_profit(self):
        return float(self.df.loc[self.df.key == 'TOTAL']['total_profit_market'])

    @property
    def winners(self):
        return self.get_winners(self.min_win_rate)

    @property
    def winners_as_pairlist(self):
        return list(self.winners.key)

    @property
    def df(self):
        df_data = self.json_data['strategy'][self.strategy]['results_per_pair']
        df = pd.DataFrame(df_data, columns=df_data[0].keys())
        df.rename(
            {
                'profit_total_abs': 'total_profit_market',
                'profit_mean': 'avg_profit_pct',
                'profit_mean_pct': 'accumulative_profit',
                'profit_total': 'total_profit_pct',
            },
            inplace=True,
            axis='columns',
        )
        return df

    @property
    def pair_performance(self):
        t_df = self.trades
        aggregation_functions = {'profit_abs': 'sum'}
        aggregate = t_df.groupby('pair').aggregate(aggregation_functions)
        for p in t_df.pair.unique():
            count = t_df.loc[t_df.pair == p].pair.count()
            volume = t_df.loc[t_df.pair == p].stake_amount.sum()
            aggregate.loc[p, 'trades'] = count
            aggregate.loc[p, 'volume'] = volume
        aggregate.trades = aggregate.trades.astype(int)
        return aggregate

    def print_winners(self):

        if not any(self.winners):
            return print('No winners')

        print(f'\n{len(self.winners)} Winner(s) (>{self.min_win_rate}%):')
        pprint(self.winners)

    @classmethod
    def from_output(cls, strategy: str, output: str, min_win_rate: float = 1, id=''):
        json_file = regex.backtest_json.findall(output)[0]
        return cls(strategy, min_win_rate=min_win_rate, json_file=json_file, id=id)

    @staticmethod
    def create_dataframe(pairs: list):
        def get_sec(time_str):
            """Get Seconds from time."""
            try:
                h, m, s = time_str.split(':')
            except ValueError:
                return '0:0:0'
            return int(h) * 3600 + int(m) * 60 + int(s)

        df = pd.DataFrame(
            pairs,
            columns=[
                'Pair',
                'Buys',
                'Average Profit',
                'Accumulative Profit',
                'Total Profit USD',
                'Total Profit %',
                'Average Duration',
                'Wins',
                'Draws',
                'Losses',
            ],
        )
        df["Average Duration"] = df["Average Duration"].apply(get_sec)
        for c in df:
            df[c] = pd.to_numeric(df[c], errors='ignore')
        return df

    @property
    def json_data(self) -> dict:
        if not self._json_data:
            self._json_data = rapidjson.loads(self.json_file.read_text())
        return self._json_data


@dataclass
class Performance:
    total: dict
    id: str
    strategy: str
    start_date: str
    end_date: str
