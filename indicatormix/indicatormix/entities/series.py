import logging
from abc import ABC
from dataclasses import dataclass

import pandas as pd

from indicatormix import State

logger = logging.getLogger(__name__)


class Series(ABC):
    series_name: str
    timeframe = ''
    append = ''

    def get(self, state: State, dataframe: pd.DataFrame):
        try:
            return dataframe[
                state.get_qualified_series_name(
                    self.series_name + self.formatted_append
                )
            ]
        except Exception as e:
            logger.info('\nseries_name: %s\ndataframe: %s', self.series_name, dataframe)
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
