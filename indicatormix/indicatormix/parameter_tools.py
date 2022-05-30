from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd
from freqtrade.strategy.parameters import BaseParameter, CategoricalParameter

from indicatormix import State
from indicatormix.constants import OPERATION, SERIES1, SERIES2, op_map
from indicatormix.custom_exceptions import BuyParametersEmpty
from indicatormix.entities.indicator import (
    IndexIndicator,
    Indicator,
    OverlayIndicator,
    SpecialValueIndicator,
)
from indicatormix.entities.series import Series

logger = logging.getLogger(__name__)


def create_local_parameters(
    state: State,
    strategy_locals: dict,
    num_buy=None,
    num_sell=None,
    buy_skip_comparisons: list[int] = None,
    sell_skip_comparisons: list[int] = None,
) -> tuple[dict, dict]:
    """
    Creates the local parameters for the strategy.

    :param state: Holds the context of the optimization.
    :param strategy_locals: The locals of the strategy.
    :param num_buy: The number of buy parameters to create.
    :param num_sell: The number of sell parameters to create.
    :param buy_skip_comparisons: The indices of the buy parameters to skip.
    :param sell_skip_comparisons: The indices of the sell parameters to skip.
    :return: The buy and sell parameters.
    """
    buy_comparisons, sell_comparisons = {}, {}
    if num_buy:
        buy_comparisons = create_comparison_groups(
            state, "buy", num_buy, buy_skip_comparisons
        )
        for n_group, p_map in buy_comparisons.items():
            for p_name, parameter in p_map.items():
                strategy_locals[f"buy_{p_name}_{n_group}"] = parameter
        logger.info(f"Created {len(buy_comparisons)} buy comparison groups.")
    if num_sell:
        sell_comparisons = create_comparison_groups(
            state, "sell", num_sell, sell_skip_comparisons
        )
        for n_group, p_map in sell_comparisons.items():
            for p_name, parameter in p_map.items():
                strategy_locals[f"sell_{p_name}_{n_group}"] = parameter
        logger.info(f"Created {len(sell_comparisons)} sell comparison groups.")
    return buy_comparisons, sell_comparisons


def create_comparison_groups(
    state: "State", type_, n_groups: int = None, skip_groups: list[int] = None
) -> dict[int, dict[str, CategoricalParameter]]:
    """
    Creates the comparison groups for the strategy.

    :param state: Holds the context of the optimization.
    :param type_: 'buy' or 'sell'.
    :param n_groups: The number of groups to create.
    :param skip_groups: The indices of the groups to skip.
    :return: The comparison groups.
    """
    logger.info(f"Creating {type_} comparison groups. Skip groups: {skip_groups}")

    comparison_groups = {}

    all_indicators = state.indicator_depot.all_columns
    ohlc_columns = get_ohlc_columns(state)
    series_columns = state.indicator_depot.overlay_indicators + ohlc_columns
    if type_ == "buy":
        if len(skip_groups) == n_groups:
            logger.warning(
                f"Skip groups are the same as number of groups. No groups will be created."
            )
            return {}
    for i in range(1, n_groups + 1):
        optimize = True
        if skip_groups and i in skip_groups:
            optimize = False
        group = {
            SERIES1: CategoricalParameter(
                all_indicators,
                default="none",
                space=type_,
                optimize=optimize,
            ),
            OPERATION: CategoricalParameter(
                list(op_map.keys()),
                default="none",
                space=type_,
                optimize=optimize,
            ),
            SERIES2: CategoricalParameter(
                series_columns, default="none", space=type_, optimize=optimize
            ),
        }
        comparison_groups[i] = group
        logger.debug(f"Created {type_} comparison group {group}.")
    return comparison_groups


def get_ohlc_columns(state: State):
    ohlc_columns = [
        "open",
        "close",
        "high",
        "low",
    ]
    tfs = state.indicator_depot.inf_timeframes
    # for each time frame in tfs, add '{col_name}_{tf}' to ohlc_columns
    for col_name in ohlc_columns.copy():
        for tf in tfs:
            ohlc_columns.append(f"{col_name}_{tf}")
    return ohlc_columns


def get_all_parameters(
    state: "State",
) -> dict[str, BaseParameter]:
    """
    Returns all parameters of the strategy.

    :param state: Holds the context of the optimization.
    :return: The parameters.
    """
    parameters = {}
    for indicator in state.indicator_depot.indicators.values():
        parameters.update(indicator.parameter_map)
    return parameters


def get_timeperiod_value(
    indicator: Indicator, strategy_locals: dict[str, BaseParameter]
) -> Optional[int]:
    """
    Returns the timeperiod value of an indicator from the strategy locals.

    :param indicator: The indicator.
    :param strategy_locals: The locals of the strategy.
    :return: The timeperiod value.
    """
    if indicator.informative:
        return
    # get optimizable parameter
    for k, val in indicator.function_kwargs.items():
        if val.optimize:
            key = k
            break
    else:
        key, _ = list(indicator.function_kwargs.items())[0]
    parameter = strategy_locals.get(f"{indicator.name}__{key}")
    if parameter:
        return parameter.value
    if key in indicator.function_kwargs:
        return indicator.function_kwargs[key].value


def apply_offset(
    state: State, series: Series, pandas_series: pd.Series, buy_or_sell: str
):
    """
    Checks the state for a custom offset value during regular optimization and applies it to the series.

    :param state: Holds the context of the optimization.
    :param series: The Series object that belongs to the IndicatorMix library.
    :param pandas_series: The pandas' series.
    :param buy_or_sell: 'buy' or 'sell'.
    :return : The series with the offset applied.
    """
    append = "offset_low" if buy_or_sell == "buy" else "offset_high"
    offset = state.custom_parameter_values.get(
        state.get_indicator_from_series(series).name + f"__{append}"
    )
    return (pandas_series * offset) if offset else pandas_series


def get_value(
    indicator: Union[IndexIndicator, SpecialValueIndicator],
    local_parameters: dict[str, BaseParameter],
    buy_or_sell: str,
):
    name = f"{indicator.name}__{buy_or_sell}"
    return local_parameters.get(name)


def get_offset_value(
    indicator: OverlayIndicator, strategy_parameters: dict, buy_or_sell: str
):
    """
    Returns the offset value of an indicator from the strategy parameters.
    Returns a default value of 1 if the offset is not set.

    :param indicator: The indicator.
    :param strategy_parameters: The parameters of the strategy.
    :param buy_or_sell: 'buy' or 'sell'.
    :return: The found offset value or 1
    """
    on = "offset_low" if buy_or_sell == "buy" else "offset_high"
    for name, parameter in strategy_parameters.items():
        if name.split("__")[0] == indicator.name and name.split("__")[1] == on:
            return parameter.value
    return 1
