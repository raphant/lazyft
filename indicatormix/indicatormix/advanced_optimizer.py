from __future__ import annotations

import logging

import pandas as pd
from freqtrade.strategy.parameters import BaseParameter

import indicatormix.entities.comparison as comparison
from indicatormix import State, condition_tools, constants
from indicatormix.custom_exceptions import InvalidComparisonError, InvalidSeriesError
from indicatormix.entities import series
from indicatormix.entities.comparison import SeriesComparison
from indicatormix.entities.indicator import IndicatorValueType
from indicatormix.parameter_tools import (
    get_offset_value,
    get_timeperiod_value,
    get_value,
)

logger = logging.getLogger(__name__)


class AdvancedOptimizer:
    """
    This class is used to do advanced optimization the found parameters of a strategy.
    """

    def __init__(
        self,
        buy_params: dict,
        sell_params: dict,
        should_optimize_values=True,
        should_optimize_offsets=True,
        should_optimize_func_kwargs=True,
        should_optimize_custom_stoploss=False,
        should_optimize_trend=True,
    ):
        """
        :param buy_params: dict of buy parameters generated in IndicatorMix
        :param sell_params: dict of sell parameters generated in IndicatorMix
        :param should_optimize_values: whether to optimize values of indicators
        :param should_optimize_offsets: whether to optimize offsets of indicators
        :param should_optimize_func_kwargs: whether to optimize function arguments of indicators
        :param should_optimize_custom_stoploss: whether to use and optimize the custom stoploss
        :param should_optimize_trend: whether to optimize the trend
        """
        self.state = State()

        self.optimize_stoploss = should_optimize_custom_stoploss
        self.optimize_values = should_optimize_values
        self.optimize_offsets = should_optimize_offsets
        self.optimize_func_kwargs = should_optimize_func_kwargs
        self.optimize_trend = should_optimize_trend

        self.buy_comparisons: list[comparison.Comparison] = []
        self.sell_comparisons: list[comparison.Comparison] = []

        self.buy_comparisons, self.sell_comparisons = self.load_custom_parameters(
            buy_params, sell_params
        )

        self.state.indicator_depot.set_active_indicators(self.get_active_indicators())

    @property
    def indicators(self):
        """
        Return the indicators of the depot

        :return: A list of indicators.
        """
        return self.state.indicator_depot.indicators

    def add_comparison_group(self, group: dict, buy_or_sell: str):
        """
        Adds a comparison group to the optimizer.

        :param group: dict of comparisons
        :param buy_or_sell: whether to add to buy or sell comparisons
        """
        # find all unique numbers in the group keys
        unique = {int(key.split("_")[-1]) for key in group.keys()}
        # split unique into groups of n_per_group
        comparisons = (
            self.buy_comparisons if buy_or_sell == "buy" else self.sell_comparisons
        )
        for i in range(min(unique), max(unique) + 1):
            series = group.pop(f"{buy_or_sell}_{constants.SERIES1}_{i}")
            op = group.pop(f"{buy_or_sell}_{constants.OPERATION}_{i}")
            compare_to = group.pop(f"{buy_or_sell}_{constants.SERIES2}_{i}")
            try:
                comparisons.append(
                    comparison.create(self.state, series, op, compare_to)
                )
            except Exception as e:
                logger.exception(
                    f"Could not create comparison {series} {op} {compare_to}",
                    exc_info=e,
                )
                raise

    def create_parameters(self) -> dict:
        """
        Creates a dict of parameters for the strategy.

        :return: dict of parameters
        """
        # get all value and function parameters from the indicators
        parameters: dict[str, BaseParameter] = {}
        for name, indicator in self.indicators.items():
            indicator_params: dict = {}
            if not indicator.informative:
                for key, val in indicator.function_kwargs.items():
                    if not self.optimize_func_kwargs:
                        val.optimize = self.optimize_func_kwargs
                indicator_params.update(indicator.function_kwargs)
            if indicator.type in [IndicatorValueType.INDEX, IndicatorValueType.OVERLAY]:
                indicator.trend_period.optimize = self.optimize_func_kwargs
                indicator_params["trend_period"] = indicator.trend_period
            if indicator.type in [
                IndicatorValueType.INDEX,
                IndicatorValueType.SPECIAL_VALUE,
            ]:
                for key, value in indicator.values.items():
                    value.optimize = self.optimize_values
                indicator_params.update(indicator.values)

            if indicator.type == IndicatorValueType.OVERLAY:
                for key, value in indicator.offsets.items():
                    value.optimize = self.optimize_offsets
                indicator_params.update(indicator.offsets)

            for key, value in {**indicator_params}.items():
                if not isinstance(value, BaseParameter):
                    continue
                parameters[f"{name}__{key}"] = value
        # get all custom stoploss parameters
        stoploss_params = constants.stoploss_params
        for key, value in stoploss_params.items():
            value.optimize = self.optimize_stoploss
        parameters.update(stoploss_params)

        return parameters

    def get_active_indicators(self):
        """
        Returns a list of active indicators from the comparisons.
        """
        indicators = {}
        for comparison in self.buy_comparisons + self.sell_comparisons:
            indicator1 = self.state.get_indicator_from_series(comparison.series1)
            indicators[indicator1.name] = indicator1
            if isinstance(comparison, SeriesComparison) and not isinstance(
                comparison.series2, series.OhlcSeries
            ):
                indicator2 = self.state.get_indicator_from_series(comparison.series2)
                if not indicator2:
                    raise KeyError(
                        f"Could not find indicator {comparison.series2.name}"
                    )
                indicators[indicator2.name] = indicator2
        return indicators

    def load_custom_parameters(
        self, buy_params: dict, sell_params: dict
    ) -> tuple[list[comparison.Comparison], list[comparison.Comparison]]:
        """
        Create comparisons for buy and sell.

        :param buy_params: dict of buy comparisons
        :param sell_params: dict of sell comparisons
        :return: tuple of buy and sell comparisons
        """
        buy_comparisons = []
        sell_comparisons = []
        # recreate the two above for loops into one
        for buy_or_sell in ["buy", "sell"]:
            comparisons = buy_comparisons if buy_or_sell == "buy" else sell_comparisons
            params = buy_params if buy_or_sell == "buy" else sell_params
            if not params:
                continue

            # find all unique numbers in the group keys
            unique = {int(key.split("_")[-1]) for key in params.keys()}

            for i in range(min(unique), max(unique) + 1):
                series = params.get(f"{buy_or_sell}_series_{i}")
                operator = params.get(f"{buy_or_sell}_operator_{i}")
                comparison_series = params.get(f"{buy_or_sell}_comparison_series_{i}")
                try:
                    comparisons.append(
                        comparison.create(
                            self.state, series, operator, comparison_series
                        )
                    )
                except (InvalidSeriesError, InvalidComparisonError) as e:
                    raise InvalidComparisonError(
                        f"Could not create comparison "
                        f'"{series} {operator} {comparison_series}": {e}'
                    ) from e

        return buy_comparisons, sell_comparisons

    def handle_series_comparison(
        self,
        dataframe: pd.DataFrame,
        comparison: comparison.SeriesComparison,
        strategy_locals: dict[str, BaseParameter],
        buy_or_sell: str,
    ) -> pd.Series:
        """
        Handle a comparison between two series

        :param dataframe: dataframe to compare
        :param comparison: comparison to handle
        :param strategy_locals: locals of the strategy
        :param buy_or_sell: 'buy' or 'sell'
        :return: series of comparison results
        """
        series1 = comparison.series1
        indicator1 = self.state.get_indicator_from_series(series1)
        timeperiod = get_timeperiod_value(indicator1, strategy_locals)
        if timeperiod:
            comparison.series1.append = timeperiod
        offset = get_offset_value(indicator1, strategy_locals, buy_or_sell)
        series1.offset = offset
        series2 = comparison.series2
        if not isinstance(series2, series.OhlcSeries):
            indicator2 = self.state.get_indicator_from_series(series2)
            timeperiod = get_timeperiod_value(indicator2, strategy_locals)
            if timeperiod:
                comparison.series2.append = timeperiod
            offset = get_offset_value(indicator2, strategy_locals, buy_or_sell)
            series2.offset = offset
        return comparison.compare(self.state, dataframe, buy_or_sell)

    def handle_value_comparison(
        self,
        dataframe: pd.DataFrame,
        comparison: comparison.ValueComparison,
        buy_or_sell: str,
        strategy_locals: dict[str, BaseParameter],
    ) -> pd.Series:
        """
        Handle a comparison between a series and a value

        :param dataframe: dataframe to compare
        :param comparison: comparison to handle
        :param buy_or_sell: 'buy' or 'sell'
        :param strategy_locals: locals of the strategy
        :return: series of comparison results
        """
        indicator1 = self.state.get_indicator_from_series(comparison.series1)
        timeperiod = get_timeperiod_value(indicator1, strategy_locals)
        if timeperiod:
            comparison.series1.append = timeperiod
        return comparison.compare(
            self.state,
            dataframe,
            buy_or_sell,
            strategy_locals.get(f"{indicator1.name}__{buy_or_sell}"),
        )

    def handle_trend_comparison(
        self,
        dataframe: pd.DataFrame,
        comparison: comparison.TrendComparison,
        buy_or_sell: str,
        strategy_locals: dict[str, BaseParameter],
    ) -> pd.Series:
        """
        Handle a comparison between a series and it's trend

        :param dataframe: dataframe to compare
        :param comparison: comparison to handle
        :param buy_or_sell: 'buy' or 'sell'
        :param strategy_locals: locals of the strategy
        :return: series of comparison results
        """
        indicator1 = self.state.get_indicator_from_series(comparison.series1)
        timeperiod = get_timeperiod_value(indicator1, strategy_locals)
        if timeperiod:
            comparison.series1.append = timeperiod
        return comparison.compare(
            self.state,
            dataframe,
            buy_or_sell,
        )

    def handle_special_value_comparison(
        self,
        dataframe: pd.DataFrame,
        comparison: comparison.SpecialValueComparison,
        buy_or_sell: str,
        strategy_locals: dict[str, BaseParameter],
    ) -> pd.Series:
        """
        Handle a comparison with a special value function

        :param dataframe: dataframe to compare
        :param comparison: comparison to handle
        :param buy_or_sell: 'buy' or 'sell'
        :param strategy_locals: locals of the strategy
        :return: series of comparison results
        """
        indicator1 = self.state.get_indicator_from_series(comparison.series1)
        timeperiod = get_timeperiod_value(indicator1, strategy_locals)
        value_parameter = get_value(indicator1, strategy_locals, buy_or_sell)

        return comparison.compare(
            self.state,
            dataframe,
            buy_or_sell,
            timeperiod,
            optimized_parameter=value_parameter,
        )

    def create_conditions(
        self, dataframe, local_parameters, buy_or_sell: str, n_per_group: int
    ) -> list[pd.Series]:
        """
        Create the conditions for the strategy

        :param dataframe: dataframe to compare
        :param local_parameters: locals of the strategy
        :param buy_or_sell: 'buy' or 'sell'
        :param n_per_group: number of conditions per group
        :return: list of series of conditions
        """
        comparisons = (
            self.buy_comparisons if buy_or_sell == "buy" else self.sell_comparisons
        )
        should_group_conditions = n_per_group > 0
        conditions = []
        for idx, comp in enumerate(comparisons):
            try:
                if isinstance(comp, comparison.SeriesComparison):
                    conditions.append(
                        self.handle_series_comparison(
                            dataframe, comp, local_parameters, buy_or_sell
                        )
                    )
                elif isinstance(comp, comparison.ValueComparison):
                    conditions.append(
                        self.handle_value_comparison(
                            dataframe, comp, buy_or_sell, local_parameters
                        )
                    )
                elif isinstance(comp, comparison.SpecialValueComparison):
                    # noinspection PyTypeChecker
                    conditions.append(
                        self.handle_special_value_comparison(
                            dataframe, comp, buy_or_sell, local_parameters
                        )
                    )
                elif isinstance(comp, comparison.PatternComparison):
                    conditions.append(comp.compare(self.state, dataframe, buy_or_sell))
                elif isinstance(comp, comparison.TrendComparison):
                    conditions.append(
                        self.handle_trend_comparison(
                            dataframe, comp, buy_or_sell, local_parameters
                        )
                    )
                else:
                    raise ValueError(f"Unhandled comparison type: {comp}")
            except Exception as e:
                logger.error(f"Error in comparison {comp.name}: {e}")
                raise e
        if not should_group_conditions:
            return conditions
        return condition_tools.group_conditions(conditions, n_per_group)
