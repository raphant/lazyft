"""
https://kaabar-sofien.medium.com/the-catapult-indicator-innovative-trading-techniques-8910ac962c57
"""
# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from numbers import Number
from pathlib import Path
from pprint import pprint
from typing import Optional, Union, Tuple

import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import pandas as pd
import pandas_ta
import talib.abstract as ta
from finta import TA
from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IntParameter,
    DecimalParameter,
    merge_informative_pair,
    CategoricalParameter,
)
from freqtrade.strategy.interface import IStrategy
from numpy import number
from pandas import DataFrame
from pandas_ta import ema
import logging
from indicator_opt import IndicatorOptHelper, indicators, Comparison, InvalidSeriesError

sys.path.append(str(Path(__file__).parent))


logger = logging.getLogger(__name__)

iopt = IndicatorOptHelper.get(3)
buy_parameters = iopt.create_parameters('buy')
sell_parameters = iopt.create_parameters('sell', 2)


class IndicatorMix(IStrategy):
    # region Parameters
    # buy
    for n_group, p_dict in buy_parameters.items():
        for p_name, parameter in p_dict.items():
            locals()[f'buy_{p_name}_{n_group}'] = parameter
    # sell
    for n_group, p_dict in sell_parameters.items():
        for p_name, parameter in p_dict.items():
            locals()[f'sell_{p_name}_{n_group}'] = parameter
    del n_group, p_name, parameter, p_dict
    # endregion
    # region Params
    minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
    stoploss = -0.25
    # endregion
    timeframe = '5m'
    use_custom_stoploss = False

    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    def informative_pairs(self) -> ListPairsWithTimeframes:
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, iopt.inf_timeframes) for pair in pairs]
        return informative_pairs

    def populate_informative_indicators(self, dataframe: DataFrame, metadata):
        inf_dfs = {}
        for timeframe in iopt.inf_timeframes:
            inf_dfs[timeframe] = self.dp.get_pair_dataframe(
                pair=metadata['pair'], timeframe=timeframe
            )

        for indicator in indicators.values():
            for timeframe in indicator.inf_timeframes:
                inf_dfs[timeframe] = indicator.populate(inf_dfs[timeframe])
        for tf, df in inf_dfs.items():
            dataframe = merge_informative_pair(dataframe, df, self.timeframe, tf)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for indicator in indicators.values():
            dataframe = indicator.populate(dataframe)
        dataframe = self.populate_informative_indicators(dataframe, metadata)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        comparisons = []
        for n_group, p_dict in buy_parameters.items():
            series = getattr(self, f'buy_series_{n_group}').value
            operator = getattr(self, f'buy_operator_{n_group}').value
            comparison_series = getattr(self, f'buy_comparison_series_{n_group}').value
            try:
                comparisons.append(
                    Comparison.create(series, operator, comparison_series)
                )
            except InvalidSeriesError:
                continue
        if not comparisons:
            return dataframe
        # combinations = iopt.combine(comparisons)
        # conditions.append(combinations)
        conditions = []
        for c in [c for c in comparisons if c]:
            conditions.append(iopt.compare(dataframe, c, 'buy'))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        comparisons = []
        for n_group, p_dict in sell_parameters.items():
            series = getattr(self, f'sell_series_{n_group}').value
            operator = getattr(self, f'sell_operator_{n_group}').value
            comparison_series = getattr(self, f'sell_comparison_series_{n_group}').value
            try:
                comparisons.append(
                    Comparison.create(series, operator, comparison_series)
                )
            except InvalidSeriesError:
                continue
        if not comparisons:
            return dataframe
        # combinations = iopt.combine(comparisons)
        # conditions.append(combinations)
        conditions = []
        for c in [c for c in comparisons if c]:
            conditions.append(iopt.compare(dataframe, c, 'sell'))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
        return dataframe
