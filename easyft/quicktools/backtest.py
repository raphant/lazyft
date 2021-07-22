import re
from pprint import pprint

import pandas as pd
from numpy import inf
from quicktools import regex


class BacktestReport:
    def __init__(
        self, data: pd.DataFrame, total_series: pd.Series, min_win_rate: float
    ) -> None:
        self.df = data
        self._totals = total_series
        self.min_win_rate = min_win_rate

    @property
    def winners(self):
        winners = self.df[self.df['Accumulative Profit'] > self.min_win_rate].copy()
        winners['WL Ratio'] = self.df['Wins'] / self.df['Losses']
        winners.loc[winners['WL Ratio'] == inf, 'WL Ratio'] = winners['Wins']
        winners['WL Ratio'] = winners['WL Ratio'].round(2)
        return winners

    @property
    def winners_as_pairlist(self):
        return list(self.winners.Pair)

    @property
    def df_with_totals(self):
        df_with_totals = self.df.append(self._totals, ignore_index=True)
        df_with_totals.loc[
            df_with_totals['Pair'] == 'TOTAL', 'Total Profit USD'
        ] = self.df['Total Profit USD'].sum()
        return df_with_totals

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
    def from_output(cls, output: str, min_win_rate: float = 0.5):
        output_string = output.split('BACKTESTING REPORT')[1]
        output_string = output_string.split('SELL REASON STATS')[0]
        total = re.findall(regex.totals, output_string)[0]
        find_pairs = re.findall(regex.pair_totals, output_string)
        df = BacktestOutputExtractor.create_dataframe(find_pairs)
        totals_series = pd.Series(total, index=df.columns)
        return cls(df, totals_series, min_win_rate)


class BacktestOutputExtractor:
    @classmethod
    def create_report(cls, output: str, min_win_rate: float) -> BacktestReport:
        """

        Args:
            output: A string of the backtest output.
            min_win_rate:

        Returns: Tuple: (DataFrame, DataFrame with totals)

        """
        output_string = output.split('BACKTESTING REPORT')[1]
        output_string = output_string.split('SELL REASON STATS')[0]
        total = re.findall(regex.totals, output_string)[0]
        find_pairs = re.findall(regex.pair_totals, output_string)
        df = cls.create_dataframe(find_pairs)
        totals_series = pd.Series(total, index=df.columns)
        return BacktestReport(df, totals_series, min_win_rate)

    @classmethod
    def get_winners(cls, df: pd.DataFrame, min_win_rate: float):
        return df[df['Accumulative Profit'] > min_win_rate].copy()

    @classmethod
    def create_dataframe(cls, pairs: list):
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
