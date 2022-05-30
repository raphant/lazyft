from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Union

import pandas as pd
from freqtrade.strategy.parameters import BaseParameter, IntParameter
from lazyft import paths

if TYPE_CHECKING:
    from indicatormix.entities.indicator import Indicator, SpecialValueIndicator
    from indicatormix.entities.series import Series
    from indicatormix.indicator_depot import IndicatorDepot
    from indicatormix.strategy import IMBaseStrategy

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# add handler and formatter to the logger
handler = logging.StreamHandler()
file_handler = logging.FileHandler(paths.LOG_DIR / "indicatormix.log")
formatter = logging.Formatter(
    "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.addHandler(file_handler)
# logger.setLevel(logging.INFO)


@dataclass
class State:
    """
    Holds all loaded indicators and parameters
    """

    timeframe: str = field(default="")
    _indicator_depot: "IndicatorDepot" = None
    series_map: dict[str, "Indicator"] = field(default_factory=dict)
    series_to_inf_series_map: dict[str, str] = field(default_factory=dict)
    custom_parameter_values: dict[str, Union[float, int]] = field(default_factory=dict)
    strategy: Optional[IMBaseStrategy] = None

    def get_qualified_series_name(self, series_name: str):
        return self.series_to_inf_series_map.get(series_name, series_name)

    def get_indicator_from_series(self, series: "Series"):
        return self.indicator_depot.get(series.series_name.split("__")[0])

    def get_trend_period(self, indicator: "Indicator") -> IntParameter:
        """
        Returns the trend of the given indicator
        Trends are named "{indicator_name}__trend_period" and will be retrieved using
        getattr on self.strategy.
        """
        return getattr(self.strategy, f"{indicator.name}__trend_period", None)

    def get_offset_value(self, indicator: "Indicator", buy_or_sell: str):
        offset = "offset_low" if buy_or_sell == "sell" else "buy"
        return getattr(self.strategy, f"{indicator.name}__{offset}", 1)

    @property
    def indicator_depot(self):
        """
        Returns the indicator depot. Creates a new one if none exists.
        """
        if self._indicator_depot is None:
            from indicatormix.indicator_depot import IndicatorDepot

            self._indicator_depot = IndicatorDepot(self.timeframe)
        return self._indicator_depot

    @property
    def indicators(self):
        return self.indicator_depot.indicators


@dataclass
class ValueFunctionArgs:
    df: pd.DataFrame
    indicator: "SpecialValueIndicator" = None
    _inf: str = ""
    _opt_timeperiod: int = None
    optimized_parameter: BaseParameter = None

    @property
    def name(self) -> str:
        """
        Returns the name of the indicator.
        """
        return self.indicator.name

    @property
    def inf(self) -> str:
        """
        Returns the indicator's timeframe if available.
        """
        return ("_" + self._inf) if self._inf else ""

    @property
    def timeperiod(self) -> str:
        """
        Returns the indicator's timeperiod during advanced optimization if available.
        """
        return ("_" + str(self._opt_timeperiod)) if self._opt_timeperiod else ""

    def get_indicator_series(self, name: str) -> pd.Series:
        """
        Returns the series with the formatted name.

        :param name: The name of the series.
        :return: The series with the formatted name.
        """
        return self.df[f"{self.name}__{name}{self.inf}{self.timeperiod}"]

    def get_series(self, name: str) -> pd.Series:
        """
        Returns the series with the direct name.

        :param name: The name of the series.
        :return: The series with the direct name.
        """
        return self.df[name]

    def get_value(self, buy_or_sell: str) -> Union[float, int]:
        """
        Returns the value of the indicator.

        :param buy_or_sell: 'buy' or 'sell'.
        :return: The value of the indicator.
        """
        if self.optimized_parameter:
            return self.optimized_parameter.value
        return self.indicator.values[buy_or_sell].value
