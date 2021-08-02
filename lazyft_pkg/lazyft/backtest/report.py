import pathlib
from pprint import pprint
from typing import Union

import pandas as pd
import rapidjson

from lazyft import regex, constants
from lazyft.strategy import Strategy


class BacktestReport:
    def __init__(
        self,
        strategy: str,
        min_win_rate: float,
        json_file: Union[str],
    ) -> None:
        self.strategy = strategy
        self.min_win_rate = min_win_rate
        self.json_file = pathlib.Path(
            constants.USER_DATA_DIR, 'backtest_results', json_file
        ).resolve()
        self._loaded_json_data = None

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
    def trades(self):
        df_data = self.json_data['strategy'][self.strategy]['trades']
        df = pd.DataFrame(df_data, columns=df_data[0].keys())
        return df

    def print_winners(self):

        if not any(self.winners):
            return print('No winners')

        print(f'\n{len(self.winners)} Winner(s) (>{self.min_win_rate}%):')
        pprint(self.winners)
        # print('Highest WL ratio:')
        # max_ratio = self.winners[
        #     self.winners['WL Ratio'] == self.winners['WL Ratio'].max()
        # ]
        # max_ratio_dict = max_ratio.to_dict(orient='records')[0]
        # pprint({max_ratio_dict.pop('Pair'): max_ratio_dict})

    @classmethod
    def from_output(cls, strategy: str, output: str, min_win_rate: float = 1):
        # output_string = output.split('BACKTESTING REPORT')[1]
        # output_string = output_string.split('SELL REASON STATS')[0]
        # total = re.findall(regex.totals, output_string)[0]
        # find_pairs = re.findall(regex.pair_totals, output_string)
        # df = cls.create_dataframe(find_pairs)
        # totals_series = pd.Series(total, index=df.columns)
        json_file = regex.backtest_json.findall(output)[0]
        return cls(strategy, min_win_rate=min_win_rate, json_file=json_file)

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
        if not self._loaded_json_data:
            self._loaded_json_data = rapidjson.loads(self.json_file.read_text())
        return self._loaded_json_data
