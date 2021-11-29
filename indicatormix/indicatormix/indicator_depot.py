from typing import Optional

from indicatormix.entities import indicator as ind
from indicatormix.indicators import (
    VALUE_INDICATORS,
    SERIES_INDICATORS,
    SPECIAL_INDICATORS,
    logger,
)


class IndicatorDepot:
    """
    Class for managing indicators.
    """

    def __init__(self) -> None:
        self._indicators: dict[str, ind.Indicator] = {
            **VALUE_INDICATORS,
            **SERIES_INDICATORS,
            **SPECIAL_INDICATORS,
        }
        self.set_indicator_names()
        self.create_informatives()

    @property
    def indicators(self) -> dict[str, ind.Indicator]:
        return self._indicators

    def get(self, indicator_name: str) -> Optional[ind.Indicator]:
        return self._indicators.get(indicator_name)

    def set_indicator_names(self) -> None:
        """
        For each indicator value in each indicator dict, set the indicator.name to its key.
        """
        for indicator_name, indicator in self._indicators.items():
            indicator.name = indicator_name

    def create_informatives(self):
        """
        Create the informative indicators using indicator.create_informatives.
        create_informatives returns a dict that we will use to update each set of indicators.
        """
        for indicator in self._indicators.copy().values():
            inf_indicators = {}
            for timeframe in indicator.inf_timeframes:
                name___timeframe = indicator.name + '_' + timeframe
                dict__ = indicator.__dict__.copy()
                dict__['name'] = name___timeframe
                try:
                    inf_indicators[name___timeframe] = ind.InformativeIndicator(
                        type=indicator.type,
                        timeframe=timeframe,
                        **dict__,
                    )
                except Exception:
                    logger.error(
                        f'Error creating InformativeIndicator {name___timeframe}'
                    )
                    raise
            self._indicators.update(inf_indicators)

    def replace_indicators(self, new_indicators: dict[str, ind.Indicator]) -> None:
        """
        Replace the indicators with a new set of indicators.
        """
        self._indicators = new_indicators

    @property
    def all_columns(self) -> list[str]:
        columns = set()
        for indicator in self._indicators.values():
            columns.update(indicator.all_columns)
        return list(columns)

    @property
    def series_indicators(self):
        """
        Get the non value/special type series
        """
        non_value_type_indicators = []
        for indicator in self._indicators.values():
            if indicator.type == ind.IndicatorType.SERIES:
                non_value_type_indicators.append(indicator)
        columns = set()
        # go through each indicator and add the `all_column` value to columns
        # if the indicator has the attribute `timeframe`, append the indicators `column_append`
        # value to the column name
        for indicator in non_value_type_indicators:
            columns.update(indicator.all_columns)
        return list(columns)

    @property
    def inf_timeframes(self) -> set[str]:
        # create inf_timeframes from all indicators
        timeframes = set()
        for indicator in self.indicators.values():
            if hasattr(indicator, 'timeframe') and indicator.timeframe != '':
                timeframes.add(indicator.timeframe)
        return timeframes
