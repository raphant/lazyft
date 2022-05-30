from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Union

import pandas as pd
from freqtrade.strategy.parameters import BaseParameter

from indicatormix import State, ValueFunctionArgs
from indicatormix.constants import op_map
from indicatormix.custom_exceptions import InvalidComparisonError, InvalidSeriesError
from indicatormix.entities.indicator import (
    IndexIndicator,
    IndicatorValueType,
    PatternIndicator,
    SpecialValueIndicator,
)
from indicatormix.entities.series import (
    IndicatorSeries,
    InformativeSeries,
    OhlcSeries,
    TrendSeries,
)
from indicatormix.parameter_tools import apply_offset, get_ohlc_columns


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

    def compare(
        self, state: "State", dataframe: pd.DataFrame, buy_or_sell: str
    ) -> pd.Series:
        pandas_series1 = self.series1.get(state, dataframe)
        operation = op_map[self.op]
        pandas_series2 = self.series2.get(state, dataframe)

        # apply offsets
        pandas_series1 = apply_offset(state, self.series1, pandas_series1, buy_or_sell)
        if not isinstance(self.series2, OhlcSeries):
            pandas_series2 = apply_offset(
                state, self.series2, pandas_series2, buy_or_sell
            )

        return operation(pandas_series1, pandas_series2)

    @property
    def name(self):
        return f"{self.series1.name} {self.op} {self.series2.name}"


@dataclass(frozen=True)
class TrendComparison(Comparison):
    series1: IndicatorSeries
    op: str
    series2: TrendSeries

    def compare(
        self, state: State, dataframe: pd.DataFrame, buy_or_sell: str, **kwargs
    ) -> pd.Series:
        # op = 'up_trend' if buy_or_sell == 'buy' else 'down_trend'
        p_series1 = self.series1.get(state, dataframe)
        operation = op_map[self.op]
        p_series2 = self.series2.get(state, dataframe)
        return operation(p_series1, p_series2)

    @property
    def name(self):
        return f"{self.series1.name} {self.op} {self.series2.name}"


@dataclass(frozen=True)
class ValueComparison(Comparison):
    series1: Union[InformativeSeries, IndicatorSeries]
    op: str

    def compare(
        self,
        state: "State",
        dataframe: pd.DataFrame,
        bs: str,
        optimized_parameter: BaseParameter = None,
    ):
        indicator: IndexIndicator = state.get_indicator_from_series(self.series1)
        operation = op_map[self.op]
        if optimized_parameter:
            value = optimized_parameter.value
        else:
            value = state.custom_parameter_values.get(
                indicator.name + f"__{bs}",
                self.get_default_value_from_indicator(bs, indicator),
            )
        return operation(self.series1.get(state, dataframe), value)

    @staticmethod
    def get_default_value_from_indicator(bs, indicator):
        parameter = indicator.values.get(bs)
        if parameter is None:
            raise InvalidComparisonError(f"{indicator.name} has no {bs} value")
        return parameter.value

    @property
    def name(self):
        return f"{self.series1.series_name} {self.op}"


@dataclass(frozen=True)
class PatternComparison(Comparison):
    series1: IndicatorSeries

    def compare(
        self,
        state: "State",
        dataframe: pd.DataFrame,
        bs: str,
    ) -> pd.Series:
        indicator: PatternIndicator = state.get_indicator_from_series(self.series1)
        value = indicator.buy if bs == "buy" else indicator.sell
        if not value:
            raise InvalidComparisonError(
                f"{self.series1.series_name} has no {bs} value"
            )
        return self.series1.get(state, dataframe) == value

    @property
    def name(self):
        return f"{self.series1.series_name}"

    # def __repr__(self) -> str:
    #     return ','.join([c.name for c in self.comparisons])


@dataclass(frozen=True)
class SpecialValueComparison(Comparison):
    series1: IndicatorSeries

    def compare(
        self,
        state: State,
        dataframe: pd.DataFrame,
        bs: str,
        opt_timeperiod=None,
        optimized_parameter: BaseParameter = None,
    ):
        """
        It gets the value function for the indicator and then calls it with the arguments.

        :param state: State
        :type state: State
        :param dataframe: The dataframe that contains the data for the indicator
        :type dataframe: pd.DataFrame
        :param bs: buy or sell
        :type bs: str
        :param opt_timeperiod: The timeperiod of the indicator that is being optimized
        :param optimized_parameter: The value that is generated by the hyperopt optimization
        :type optimized_parameter: BaseParameter
        :return: A value.
        """
        indicator: SpecialValueIndicator = state.get_indicator_from_series(self.series1)
        value_func = indicator.value_function.get(bs)
        if not value_func:
            raise InvalidComparisonError(
                f"{self.series1.series_name} has no {bs} value"
            )
        result = indicator.value_function[bs](
            ValueFunctionArgs(
                dataframe,
                indicator,
                indicator.timeframe,
                opt_timeperiod,
                optimized_parameter,
            )
        )
        return result

    @property
    def name(self):
        return self.series1.series_name


def create(
    state: "State",
    series_name: str,
    op_str: str,
    comparison_series_name: str,
) -> Optional["Comparison"]:
    """
    Create a comparison object from the parameters in the strategy during hyperopt
    """
    if series_name == "none":
        raise InvalidSeriesError(f"Series {series_name} is not defined")
    # series1_indicator = state.indicator_depot.get(series_name.split('__')[0])
    series1 = IndicatorSeries(series_name)
    series1_indicator = state.get_indicator_from_series(series1)
    if not series1_indicator:
        raise KeyError(f"{series_name} is not a valid indicator")
    # deal with special types first
    if series1_indicator.type == IndicatorValueType.PATTERN:
        return PatternComparison(series1)
    elif series1_indicator.type == IndicatorValueType.SPECIAL_VALUE:
        return SpecialValueComparison(series1)

    if op_str in ["UT", "DT", "CDT", "CUT"]:
        if not series1_indicator.check_trend or series1_indicator.informative:
            raise InvalidComparisonError(
                f"{series_name} does not support trend comparison"
            )
        series2 = TrendSeries(series1)
        return TrendComparison(series1, op_str, series2)
    if series1_indicator.type == IndicatorValueType.INDEX:
        return ValueComparison(series1, op_str)
    if series_name == comparison_series_name or comparison_series_name == "none":
        raise InvalidComparisonError(
            f"Series {series_name} cannot be compared to itself"
        )
    # create OhlcSeries if the comparison series is in ohlc
    if comparison_series_name in get_ohlc_columns(state):
        comparison_series = OhlcSeries(comparison_series_name)
    # elif state.series_map[comparison_series_name].timeframe:
    #     comparison_series = InformativeSeries(
    #         comparison_series_name,
    #         timeframe=state.series_map[comparison_series_name].timeframe,
    #     )
    else:
        comparison_series = IndicatorSeries(comparison_series_name)
        # make sure series2 indicator is in the active list
        state.get_indicator_from_series(comparison_series)
    return SeriesComparison(series1, op_str, comparison_series)
