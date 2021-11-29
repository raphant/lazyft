from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from indicatormix.entities.indicator import Indicator
    from indicatormix.indicator_depot import IndicatorDepot
    from indicatormix.entities.series import Series


@dataclass
class State:
    """
    Holds the necessary information to run
    """

    indicator_depot: 'IndicatorDepot'
    series_map: dict[str, 'Indicator'] = field(default_factory=dict)
    parameter_map: dict[str, 'Indicator'] = field(default_factory=dict)
    series_to_inf_series_map: dict[str, str] = field(default_factory=dict)

    def get_qualified_series_name(self, series_name: str):
        return self.series_to_inf_series_map.get(series_name, series_name)

    def get_indicator_from_series(self, series: 'Series'):
        return self.indicator_depot.get(series.series_name.split('__')[0])


@dataclass
class ValueFunctionArgs:
    df: pd.DataFrame
    name: str
    _inf: str = ''
    _opt_timeperiod: int = None

    @property
    def inf(self):
        return ('_' + self._inf) if self._inf else ''

    @property
    def timeperiod(self):
        return ('_' + str(self._opt_timeperiod)) if self._opt_timeperiod else ''
