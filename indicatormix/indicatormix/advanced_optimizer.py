import logging

import pandas as pd
from freqtrade.strategy.hyper import BaseParameter

import indicatormix.entities.comparison as comparison
from indicatormix import State
from indicatormix.conditions import Conditions
from indicatormix.entities.comparison import SeriesComparison
from indicatormix.entities.indicator import ValueIndicator
from indicatormix.indicator_depot import IndicatorDepot
from indicatormix.parameter_tools import ParameterTools

logger = logging.getLogger(__name__)


class AdvancedOptimizer:
    def __init__(self, buy_params: dict, sell_params: dict):
        self.state = State(IndicatorDepot())
        self.buy_comparisons: list[comparison.Comparison] = []
        self.sell_comparisons: list[comparison.Comparison] = []
        logger.info("Filling parameter map")
        self.state.parameter_map.update(ParameterTools.get_all_parameters(self.state))
        self.buy_comparisons, self.sell_comparisons = self.load_custom_parameters(
            buy_params, sell_params
        )
        self.state.indicator_depot.replace_indicators(self.get_active_indicators())

    @property
    def indicators(self):
        return self.state.indicator_depot.indicators

    def create_parameters(self) -> dict:
        # get all value and function parameters from the indicators
        parameters = {}
        for name, indicator in self.indicators.items():
            if indicator.informative:
                continue
            func_params = indicator.function_kwargs
            value_params = {}
            if isinstance(indicator, ValueIndicator):
                value_params = indicator.values
            for key, value in {**func_params, **value_params}.items():
                if not isinstance(value, BaseParameter):
                    continue
                parameters[f"{name}__{key}"] = value
                self.state.parameter_map[f"{name}__{key}"] = indicator
        return parameters

    def get_active_indicators(self):
        indicators = {}
        for comparison in self.buy_comparisons + self.sell_comparisons:
            indicator1 = self.state.get_indicator_from_series(comparison.series1)
            indicators[indicator1.name] = indicator1
            if isinstance(comparison, SeriesComparison):
                indicator2 = self.state.get_indicator_from_series(comparison.series2)
                indicators[indicator2.name] = indicator2
        return indicators

    def load_custom_parameters(
        self, buy_params: dict, sell_params: dict
    ) -> tuple[list[comparison.Comparison], list[comparison.Comparison]]:
        """
        Create comparisons for buy and sell
        """
        buy_comparisons = []
        sell_comparisons = []
        i = 1
        # buy
        while any(buy_params):
            if f'buy_comparison_series_{i}' in buy_params:
                # pop from params
                buy_series = buy_params.pop(f'buy_series_{i}')
                by_op = buy_params.pop(f'buy_operator_{i}')
                buy_compare_to = buy_params.pop(f'buy_comparison_series_{i}')

                buy_comparisons.append(
                    comparison.create(self.state, buy_series, by_op, buy_compare_to)
                )
            i += 1
        # sell
        i = 1
        while any(sell_params):
            if f'sell_comparison_series_{i}' in sell_params:
                sell_series = sell_params.pop(f'sell_series_{i}')
                sell_operator = sell_params.pop(f'sell_operator_{i}')
                sell_comparison_series = sell_params.pop(f'sell_comparison_series_{i}')
                try:
                    sell_comparisons.append(
                        comparison.create(
                            self.state,
                            sell_series,
                            sell_operator,
                            sell_comparison_series,
                        )
                    )
                except Exception as e:
                    raise e.__class__(
                        f'Error creating sell comparison {sell_series} {sell_operator} {sell_comparison_series}'
                    )
            i += 1
        return buy_comparisons, sell_comparisons

    def handle_series_comparison(
        self,
        dataframe: pd.DataFrame,
        comparison: comparison.SeriesComparison,
        strategy_locals: dict[str, BaseParameter],
    ):
        series1 = comparison.series1
        indicator1 = self.state.get_indicator_from_series(series1)
        timeperiod = self.get_timeperiod_value(indicator1, strategy_locals)
        if timeperiod:
            comparison.series1.append = timeperiod

        series2 = comparison.series2
        indicator2 = self.state.get_indicator_from_series(series2)
        timeperiod = self.get_timeperiod_value(indicator2, strategy_locals)
        if timeperiod:
            comparison.series2.append = timeperiod

        return comparison.compare(self.state, dataframe)

    def handle_value_comparison(
        self,
        dataframe: pd.DataFrame,
        comparison: comparison.ValueComparison,
        buy_or_sell: str,
        strategy_locals: dict[str, BaseParameter],
    ):
        indicator1 = self.state.get_indicator_from_series(comparison.series1)
        timeperiod = self.get_timeperiod_value(indicator1, strategy_locals)
        if timeperiod:
            comparison.series1.append = timeperiod
        return comparison.compare(
            self.state,
            dataframe,
            buy_or_sell,
            strategy_locals[f'{indicator1.name}__{buy_or_sell}'],
        )

    def handle_special_value_comparison(
        self,
        dataframe: pd.DataFrame,
        comparison: comparison.SpecialValueComparison,
        buy_or_sell: str,
        strategy_locals: dict[str, BaseParameter],
    ):
        indicator1 = self.state.get_indicator_from_series(comparison.series1)
        timeperiod = self.get_timeperiod_value(indicator1, strategy_locals)

        return comparison.compare(self.state, dataframe, buy_or_sell, timeperiod)

    @staticmethod
    def get_timeperiod_value(indicator, strategy_locals):
        for name, parameter in strategy_locals.items():
            if name.startswith(indicator.name):
                if name.split("__")[1] == 'timeperiod':
                    return parameter.value

    def create_conditions(
        self, dataframe, local_parameters, buy_or_sell: str, n_per_group: int
    ):
        comparisons = (
            self.buy_comparisons if buy_or_sell == 'buy' else self.sell_comparisons
        )
        conditions = []
        for comp in comparisons:
            if isinstance(comp, comparison.SeriesComparison):
                conditions.append(
                    self.handle_series_comparison(
                        dataframe,
                        comp,
                        local_parameters,
                    )
                )
            elif isinstance(comp, comparison.ValueComparison):
                conditions.append(
                    self.handle_value_comparison(
                        dataframe, comp, buy_or_sell, local_parameters
                    )
                )
            else:
                # noinspection PyTypeChecker
                conditions.append(
                    self.handle_special_value_comparison(
                        dataframe, comp, buy_or_sell, local_parameters
                    )
                )
        if n_per_group == 0:
            return conditions
        return Conditions.group_conditions(conditions, n_per_group)


if __name__ == '__main__':

    optimizer = AdvancedOptimizer()
    print(optimizer.create_parameters())
