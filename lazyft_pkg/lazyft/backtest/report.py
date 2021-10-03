import pathlib
from pprint import pprint
from typing import Union

import pandas as pd
import rapidjson

from lazyft import paths
from lazyft.models import (
    BacktestPerformance,
    BacktestReport,
    BacktestData,
)
from lazyft.strategy import StrategyTools


class BacktestReportExporter:
    def __init__(
        self,
        strategy: str,
        json_file: Union[str],
        hash: str,
        # balance_info: dict,
        report_id: str,
        hyperopt_id: str = None,
        min_win_rate=1,
        exchange: str = '',
        pairlist=None,
        tag=None,
        ensemble=None,
    ) -> None:
        self.strategy = strategy
        self.min_win_rate = min_win_rate
        self.hash = hash
        self.json_file = pathlib.Path(
            paths.USER_DATA_DIR, 'backtest_results', json_file
        ).resolve()
        self.exchange = exchange
        self._json_data = None
        self.hyperopt_id = hyperopt_id
        self.report_id = report_id
        # self.balance_info = balance_info
        self.pairs = pairlist
        self.tag = tag
        self.ensemble = ensemble

    @property
    def report(self):
        report = BacktestReport(
            strategy=self.strategy,
            backtest_data=BacktestData(data=self.json_file.read_text()),
            hash=self.hash,
            report_id=self.report_id,
            param_id=self.hyperopt_id,
            performance=self.performance,
            exchange=self.exchange,
            tag=self.tag,
            ensemble=self.ensemble or '',
        )
        return report

    @property
    def performance(self):
        to_dict = self.totals.to_dict(orient='records')[0]
        to_dict.pop('key')
        start_date = self.json_data['strategy'][self.strategy]['backtest_start']
        end_date = self.json_data['strategy'][self.strategy]['backtest_end']
        performance = BacktestPerformance(
            **to_dict,
            start_date=start_date,
            end_date=end_date,
        )
        return performance

    def add_super_earners_to_whitelist(self, pct: float):
        StrategyTools.add_pairs_to_whitelist(
            self.strategy, *list(self.get_winners(pct).key)
        )

    def add_super_losers_to_blacklist(self, pct: float):
        StrategyTools.add_pairs_to_blacklist(
            self.strategy, *list(self.get_losers(pct).key)
        )

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
        if self.hyperopt_id:
            key = key + f'-{self.hyperopt_id}'
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
