from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Union

from freqtrade.strategy.parameters import BaseParameter, DecimalParameter, IntParameter
from pandas import DataFrame, Series

from indicatormix import ValueFunctionArgs

logger = logging.getLogger()


class IndicatorValueType(Enum):
    INDEX = "index"
    OVERLAY = "overlay"
    SPECIAL_VALUE = "special_value"
    PATTERN = "pattern"


class Indicator:
    type = ""
    timeframe = ""

    def __init__(
        self,
        func: Callable,
        columns: list[str],
        func_columns=None,
        function_kwargs: dict = None,
        inf_timeframes=None,
        name="",
        check_trend=False,
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
        self.check_trend = check_trend
        self.trend_period = IntParameter(2, 10, default=4, space="buy")
        self.__dict__.update(kwargs)

    @property
    def formatted_columns(self):
        return [f"{self.name}__{c}" for c in self.columns]

    @property
    def all_columns(self):
        return self.formatted_columns

    @property
    def parameter_map(self):
        parameters = {**self.function_kwargs}
        return {f"{self.name}__{k}": v for k, v in parameters.items()}

    def __str__(self):
        return f"{self.__class__.__name__} - {self.name}"

    def __repr__(self):
        return f"{self.__class__.__name__} - {self.name}"


class IndexIndicator(Indicator):
    type = IndicatorValueType.INDEX

    def __init__(self, values: dict[str, BaseParameter], **kwargs) -> None:
        super().__init__(**kwargs)
        self.values = values

    @property
    def parameter_map(self):
        parameters = {**self.values, **self.function_kwargs}
        return {f"{self.name}__{k}": v for k, v in parameters.items()}

    def get_value(self, buy_or_sell: str):
        return self.values[buy_or_sell]


class OverlayIndicator(Indicator):
    type = IndicatorValueType.OVERLAY

    def __init__(
        self,
        offsets: dict = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.offsets = offsets or {
            "offset_low": DecimalParameter(
                0.9, 1, default=1, space="buy", optimize=True
            ),
            "offset_high": DecimalParameter(
                0.95, 1.5, default=1, space="sell", optimize=True
            ),
        }
        self.check_trend = True


class SpecialValueIndicator(Indicator):
    type = IndicatorValueType.SPECIAL_VALUE

    def __init__(
        self,
        value_functions: dict[
            str, Callable[[ValueFunctionArgs], Union[Series, DataFrame]]
        ],
        values: dict[str, BaseParameter] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.value_function = value_functions
        self.values = values or {}


class InformativeIndicator(Indicator):
    def __init__(self, type: str, timeframe: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.timeframe = timeframe
        self.type = type
        self.column_append = "_" + timeframe
        self.informative = True


class PatternIndicator(Indicator):
    type = IndicatorValueType.PATTERN

    def __init__(self, buy=None, sell=None, **kwargs) -> None:
        super().__init__(
            columns=["value"], func_columns=["open", "high", "low", "close"], **kwargs
        )
        self.buy = buy
        self.sell = sell
