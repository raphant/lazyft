import logging
from abc import ABC
from dataclasses import dataclass

import pandas as pd

from indicatormix import State
import talib as ta

logger = logging.getLogger(__name__)


class Series(ABC):
    series_name: str
    timeframe = ''
    append = ''
    offset = 1

    def get(self, state: State, dataframe: pd.DataFrame) -> pd.Series:
        try:
            return dataframe[
                state.get_qualified_series_name(self.series_name + self.formatted_append)
            ] * float(self.offset or 1)
        except Exception as e:
            logger.info('\nseries_name: %s\n columns: %s', self.series_name, dataframe.columns)
            logger.exception(e)
            raise

    @property
    def formatted_append(self):
        return ('_' + str(self.append)) if self.append else ''

    @property
    def name(self):
        return self.series_name


@dataclass
class InformativeSeries(Series):
    series_name: str
    timeframe: str

    def get(self, state: State, dataframe: pd.DataFrame):

        try:
            return dataframe[state.get_qualified_series_name(self.series_name)]
        except Exception:
            logger.info('\nseries_name: %s\ndataframe: %s', self.series_name, dataframe)
            raise KeyError(
                f'{self.series_name + "_" + self.timeframe} not found in '
                f'dataframe. Available columns: {dataframe.columns}'
            )


@dataclass
class IndicatorSeries(Series):
    series_name: str


@dataclass
class OhlcSeries(Series):
    series_name: str


@dataclass
class TrendSeries(Series):
    base_series: Series

    @property
    def series_name(self):
        return self.base_series.series_name + '_trend'

    def get(self, state: State, dataframe: pd.DataFrame) -> pd.Series:
        indicator = state.get_indicator_from_series(self.base_series)
        trend_period = state.get_trend_period(indicator)
        if not trend_period:
            trend_period = 4
        else:
            trend_period = trend_period.value
        name = f'{self.series_name}__trend_{trend_period}'
        if name not in dataframe.columns:
            series = self.base_series.get(state, dataframe)
            dataframe[name] = ta.SMA(series, timeperiod=trend_period)
        return dataframe[name]
