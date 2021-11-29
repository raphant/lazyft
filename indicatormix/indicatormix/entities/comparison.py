from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Union, Any

import pandas as pd
from freqtrade.strategy.hyper import BaseParameter

from indicatormix import State, ValueFunctionArgs
from indicatormix.constants import op_map
from indicatormix.custom_exceptions import InvalidSeriesError
from indicatormix.entities.indicator import (
    SeriesIndicator,
    InformativeIndicator,
    SpecialIndicator,
    ValueIndicator,
    IndicatorType,
    SpecialValueIndicator,
)
from indicatormix.entities.series import IndicatorSeries, InformativeSeries, OhlcSeries


@dataclass(frozen=True)
class Comparison(ABC):
    series1: IndicatorSeries

    @abstractmethod
    def compare(self, *args, **kwargs) -> pd.Series:
        pass


@dataclass(frozen=True)
class SeriesComparison(Comparison):
    series1: Union[IndicatorSeries, InformativeSeries]
    op: str
    series2: Union[IndicatorSeries, OhlcSeries, InformativeSeries]

    def compare(self, state: 'State', dataframe: pd.DataFrame, *args):
        series1 = self.series1.get(state, dataframe)
        operation = op_map[self.op]
        series2 = self.series2.get(state, dataframe)
        return operation(series1, series2)

    @property
    def name(self):
        return f'{self.series1.series_name} {self.op} {self.series2.name}'


@dataclass(frozen=True)
class ValueComparison(Comparison):
    series1: Union[InformativeSeries, IndicatorSeries]
    op: str

    def compare(
        self,
        state: 'State',
        dataframe: pd.DataFrame,
        bs: str,
        optimized_parameter: BaseParameter = None,
    ):
        indicator: ValueIndicator = state.get_indicator_from_series(self.series1)
        operation = op_map[self.op]
        if optimized_parameter:
            value = optimized_parameter.value
        else:
            value = indicator.values[bs].value
        return operation(
            self.series1.get(state, dataframe),
            value,
        )

    @property
    def name(self):
        return f'{self.series1.series_name} {self.op}'

    # def __repr__(self) -> str:
    #     return ','.join([c.name for c in self.comparisons])


@dataclass(frozen=True)
class SpecialValueComparison(Comparison):
    series1: Union[IndicatorSeries]

    def compare(
        self, state: State, dataframe: pd.DataFrame, bs: str, opt_timeperiod=None
    ):
        indicator: SpecialValueIndicator = state.get_indicator_from_series(self.series1)
        result = indicator.value_function[bs](
            ValueFunctionArgs(
                dataframe, indicator.name, indicator.timeframe, opt_timeperiod
            )
        )
        return result

    # def __repr__(self) -> str:
    #     return ','.join([c.name for c in self.comparisons])


def create(
    state: 'State',
    series_name: str,
    op_str: str,
    comparison_series_name: str,
) -> Optional['Comparison']:
    """
    Create a comparison object from the parameters in the strategy during hyperopt
    """
    if series_name == 'none' or series_name == comparison_series_name:
        raise InvalidSeriesError()
    series1_indicator = state.indicator_depot.get(series_name.split('__')[0])

    if series1_indicator.type == 'none':
        raise InvalidSeriesError()
    # if series1_indicator.informative:
    #     series1 = InformativeSeries(series_name, timeframe=series1_indicator.timeframe)
    # else:
    series1 = IndicatorSeries(series_name)
    # return comparison based on the compare type
    if series_name == 'none':
        raise InvalidSeriesError()
    if series1_indicator.type == IndicatorType.VALUE:
        return ValueComparison(series1, op_str)
    elif series1_indicator.type.value == IndicatorType.SPECIAL_VALUE.value:
        return SpecialValueComparison(series1)

    if series1_indicator.type == IndicatorType.SPECIAL:
        # here we have a SpecialIndicator. They will only be compared to preconfigured values
        # in indicator.compare. We may get the key or value of indicator.compare, so we will
        # flip the compare dict if we have to.
        compare = series1_indicator.formatted_compare.copy()
        # name_split = series_name.split('__')[1]
        if series_name not in compare:
            # flip the compare dict
            compare = {v: k for k, v in compare.items()}
            if comparison_series_name not in compare:
                raise InvalidSeriesError()

        comparison_series_name = compare[series_name]
        comparison_series = IndicatorSeries(comparison_series_name)
    # create OhlcSeries if the comparison series is in ohlc
    elif comparison_series_name in ['open', 'high', 'low', 'close']:
        comparison_series = OhlcSeries(comparison_series_name)
    # elif state.series_map[comparison_series_name].timeframe:
    #     comparison_series = InformativeSeries(
    #         comparison_series_name,
    #         timeframe=state.series_map[comparison_series_name].timeframe,
    #     )
    else:
        comparison_series = IndicatorSeries(comparison_series_name)
    return SeriesComparison(series1, op_str, comparison_series)
