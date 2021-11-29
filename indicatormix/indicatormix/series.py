import logging
from abc import ABC

from pandas import DataFrame
from pydantic.dataclasses import dataclass

logger = logging.getLogger(__name__)


class ISeries(ABC):
    series_name: str

    def get(self, dataframe: DataFrame):
        try:
            return dataframe[self.series_name]
        except Exception as e:
            logger.error(
                '\nseries_name: %s\ndataframe: %s', self.series_name, dataframe
            )
            logger.exception(e)
            raise

    @property
    def name(self):
        return self.series_name


@dataclass
class InformativeSeries(ISeries):
    series_name: str
    timeframe: str

    def get(self, dataframe: DataFrame):
        try:
            return dataframe[self.series_name + '_' + self.timeframe]
        except Exception:
            logger.error(
                '\nseries_name: %s\ndataframe: %s', self.series_name, dataframe
            )
            raise KeyError(
                f'{self.series_name + "_" + self.timeframe} not found in '
                f'dataframe. Available columns: {dataframe.columns}'
            )


@dataclass(frozen=True)
class IndicatorSeries(ISeries):
    series_name: str


@dataclass(frozen=True)
class OhlcSeries(ISeries):
    series_name: str
