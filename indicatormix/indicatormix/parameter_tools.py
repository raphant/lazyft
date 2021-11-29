import logging
from typing import Optional

from freqtrade.strategy import CategoricalParameter

from indicatormix import State
from indicatormix.constants import op_map
from indicatormix.entities.indicator import Indicator

logger = logging.getLogger(__name__)


class ParameterTools:
    @staticmethod
    def get_all_parameters(
        state: 'State',
    ) -> dict:
        parameters = {}
        for indicator in state.indicator_depot.indicators.values():
            parameters.update(indicator.parameter_map)
        return parameters

    @staticmethod
    def get_indicator_from_parameter_name(
        state: 'State', parameter_name: str
    ) -> Optional[Indicator]:
        return state.parameter_map.get(parameter_name)

    @staticmethod
    def create_comparison_groups(
        state: 'State', type_, n_groups: int = None, skip_groups: list[int] = None
    ) -> dict[int, dict[str, CategoricalParameter]]:
        logger.info('creating group parameters')

        comparison_groups = {}

        all_indicators = state.indicator_depot.all_columns
        series = state.indicator_depot.series_indicators + [
            'open',
            'close',
            'high',
            'low',
        ]
        for i in range(1, n_groups + 1):
            optimize = True
            if skip_groups and i in skip_groups:
                optimize = False
            group = {
                'series': CategoricalParameter(
                    all_indicators,
                    default='none',
                    space=type_,
                    optimize=optimize,
                ),
                'operator': CategoricalParameter(
                    list(op_map.keys()),
                    default='none',
                    space=type_,
                    optimize=optimize,
                ),
                'comparison_series': CategoricalParameter(
                    series, default='none', space=type_, optimize=optimize
                ),
            }
            comparison_groups[i] = group
        return comparison_groups

    @staticmethod
    def create_local_parameters(
        state: 'State',
        strategy_locals: dict,
        num_buy=None,
        num_sell=None,
        buy_skip_groups: list[int] = None,
        sell_skip_groups: list[int] = None,
    ) -> tuple[dict, dict]:
        buy_comparisons, sell_comparisons = {}, {}
        if num_buy:
            buy_comparisons = ParameterTools.create_comparison_groups(
                state, 'buy', num_buy, buy_skip_groups
            )
            for n_group, p_map in buy_comparisons.items():
                for p_name, parameter in p_map.items():
                    strategy_locals[f'buy_{p_name}_{n_group}'] = parameter
        if num_sell:
            sell_comparisons = ParameterTools.create_comparison_groups(
                state, 'sell', num_sell, sell_skip_groups
            )
            for n_group, p_map in sell_comparisons.items():
                for p_name, parameter in p_map.items():
                    strategy_locals[f'sell_{p_name}_{n_group}'] = parameter
        return buy_comparisons, sell_comparisons
