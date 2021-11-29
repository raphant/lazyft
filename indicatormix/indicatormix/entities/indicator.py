from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Union

from freqtrade.strategy.hyper import (
    BaseParameter,
)
from pandas import DataFrame, Series

from indicatormix import ValueFunctionArgs

logger = logging.getLogger()


class IndicatorType(Enum):
    VALUE = 'value'
    SERIES = 'series'
    SPECIAL = 'special'
    SPECIFIC = 'specific'
    SPECIAL_VALUE = 'special_value'


class Indicator:
    type = ''
    timeframe = ''

    def __init__(
        self,
        func: Callable,
        columns: list[str],
        func_columns=None,
        function_kwargs: dict = None,
        inf_timeframes=None,
        name='',
        **kwargs,
    ) -> None:
        self.func = func
        if not function_kwargs:
            function_kwargs = {}
        self.function_kwargs: dict[
            str, Union[int, float, BaseParameter]
        ] = function_kwargs
        self.func_columns = func_columns or []
        self.columns = columns
        self.inf_timeframes = inf_timeframes or []
        self.name = name
        self.informative = False
        self.__dict__.update(kwargs)

    @property
    def formatted_columns(self):
        return [f'{self.name}__{c}' for c in self.columns]

    @property
    def all_columns(self):
        return self.formatted_columns

    @property
    def parameter_map(self):
        parameters = {**self.function_kwargs}
        return {f'{self.name}__{k}': v for k, v in parameters.items()}

    def __str__(self):
        return f'{self.__class__.__name__} - {self.name}'

    def __repr__(self):
        return f'{self.__class__.__name__} - {self.name}'


class ValueIndicator(Indicator):
    type = IndicatorType.VALUE

    def __init__(self, values: dict[str, BaseParameter], **kwargs) -> None:
        super().__init__(**kwargs)
        self.values = values

    @property
    def parameter_map(self):
        parameters = {**self.values, **self.function_kwargs}
        return {f'{self.name}__{k}': v for k, v in parameters.items()}

    def get_value(self, buy_or_sell: str):
        return self.values[buy_or_sell]


class SeriesIndicator(Indicator):
    type = IndicatorType.SERIES


class SpecialIndicator(Indicator):
    """These indicators will only be compared to indicators created by its TA function"""

    type = IndicatorType.SPECIAL

    def __init__(self, compare: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.compare = compare

    @property
    def formatted_compare(self):
        """
        Return a dict of the compare dict with the keys formatted to the
        format of the columns in the dataframe.
        """
        return {
            f'{self.name}__{k}': f'{self.name}__{v}' for k, v in self.compare.items()
        }


class SpecialValueIndicator(Indicator):
    type = IndicatorType.SPECIAL_VALUE

    def __init__(
        self,
        value_functions: dict[str, Callable[[ValueFunctionArgs], Union[Series, DataFrame]]],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.value_function = value_functions


class SpecificIndicator(Indicator):
    """These indicators will only be compared to other specified indicators"""

    type = IndicatorType.SPECIFIC

    def __init__(self, compare: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.compare = compare


class InformativeIndicator(Indicator):
    def __init__(self, type: str, timeframe: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.timeframe = timeframe
        self.type = type
        self.column_append = '_' + timeframe
        self.informative = True
