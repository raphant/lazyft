"""
Defines the IndicatorDepot class.
"""
from __future__ import annotations

import logging
from typing import Optional, Union

from indicatormix.entities import indicator as ind
from indicatormix.indicators import (
    INDEX_INDICATORS,
    OVERLAY_INDICATORS,
    PATTERN_INDICATORS,
    SPECIAL_INDICATORS,
)
from indicatormix.misc import is_bigger_timeframe

logger = logging.getLogger(__name__)


class IndicatorDepot:
    """
    Class for managing indicators.
    """

    def __init__(self, timeframe: str = None) -> None:
        self._indicators: dict[str, ind.Indicator] = {
            **INDEX_INDICATORS,
            **OVERLAY_INDICATORS,
            **SPECIAL_INDICATORS,
            **PATTERN_INDICATORS,
        }
        self.set_indicator_names()
        self.create_informatives(timeframe)
        self._active_indicators: dict[str, ind.Indicator] = self._indicators.copy()

    @property
    def indicators(
        self,
    ) -> dict[str, Union[ind.Indicator, ind.OverlayIndicator, ind.IndexIndicator]]:
        """
        Returns a dictionary of all the active indicators
        :return: A dictionary of indicator objects.
        """
        return self._active_indicators

    def get(self, indicator_name: str) -> Optional[Union[ind.OverlayIndicator, ind.IndexIndicator]]:
        """
        Retrieve an indicator by name.
        If the indicator is not in the active indicators, it will be added to the active indicators

        :param indicator_name: str
        :type indicator_name: str
        :return: An indicator object.
        """
        # logger.debug(f'Getting indicator {indicator_name}')
        indicator = self._active_indicators.get(indicator_name)
        if indicator is None:
            indicator = self._indicators.get(indicator_name)
            if not indicator:
                logger.debug(f'Indicator {indicator_name} not found.')
                return None
            # add the indicator to the active indicators
            self._active_indicators[indicator.name] = indicator
            logger.debug(f'Added indicator {indicator_name} to active indicators.')
        if indicator is None:
            logger.error(f'Indicator {indicator_name} not found.')
        return indicator

    def set_indicator_names(self) -> None:
        """
        For each indicator value in each indicator dict, set the indicator.name to its key.
        """
        for indicator_name, indicator in self._indicators.items():
            indicator.name = indicator_name

    def create_informatives(self, strategy_timeframe: str) -> None:
        """
        Create the informative indicators using indicator.create_informatives.
        create_informatives returns a dict that we will use to update each set of indicators.
        """
        inf_indicators = {}

        for indicator in self._indicators.copy().values():
            for timeframe in indicator.inf_timeframes:
                if strategy_timeframe and is_bigger_timeframe(strategy_timeframe, timeframe):
                    # skip if the timeframe is smaller than the strategy timeframe
                    logger.debug(f'Skipping {indicator.name} @ {timeframe}.')
                    continue
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
                    logger.error(f'Error creating InformativeIndicator {name___timeframe}')
                    raise
        self._indicators.update(inf_indicators)

    def set_active_indicators(self, new_indicators: dict[str, ind.Indicator]) -> None:
        """
        Set the active indicators to the new indicators.
        """
        self._active_indicators = new_indicators

    @property
    def all_columns(self) -> list[str]:
        """
        Return a list of all the columns that are used by any of the indicators in the strategy
        :return: A list of strings.
        """
        columns = set()
        for indicator in self._indicators.values():
            columns.update(indicator.all_columns)
        return list(columns)

    @property
    def overlay_indicators(self):
        """
        Get the non value/special type series
        """
        non_value_type_indicators = []
        for indicator in self._indicators.values():
            if indicator.type == ind.IndicatorValueType.OVERLAY:
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
        """
        The function inf_timeframes() takes the indicators from the strategy and creates a set of all
        the timeframes used by the indicators
        :return: A set of strings.
        """
        # create inf_timeframes from all indicators
        timeframes = set()
        for indicator in self.indicators.values():
            if hasattr(indicator, 'timeframe') and indicator.timeframe != '':
                timeframes.add(indicator.timeframe)
        return timeframes
