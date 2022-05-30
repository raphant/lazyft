import operator
from functools import partial

import pandas as pd
from freqtrade.strategy.parameters import DecimalParameter

from indicatormix.entities.indicator import IndicatorValueType
from indicatormix.helpers import custom_indicators as ci


def compare_trend(
    series: pd.Series, series_trend: pd.Series, up_trend=True, crossed=False
):
    if up_trend:
        if crossed:
            return ci.crossed_above(series, series_trend)
        return series > series_trend
    if crossed:
        return ci.crossed_below(series, series_trend)
    return series < series_trend


trend_ops = {
    "UT": partial(compare_trend, up_trend=True),
    "DT": partial(compare_trend, up_trend=False),
    "CUT": partial(compare_trend, up_trend=True, crossed=True),
    "CDT": partial(compare_trend, up_trend=False, crossed=True),
}
crossed_ops = {
    "crossed_above": ci.crossed_above,
    "crossed_below": ci.crossed_below,
}
op_map = {
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
    **trend_ops,
    **crossed_ops,
}
VALUE_TYPE = [IndicatorValueType.INDEX, IndicatorValueType.SPECIAL_VALUE]
stoploss_params = {
    # hard stoploss profit
    "pHSL": DecimalParameter(
        -0.20,
        -0.040,
        default=-0.20,
        decimals=3,
        space="sell",
        optimize=False,
    ),
    # profit threshold 1, trigger point, SL_1 is used
    "pPF_1": DecimalParameter(
        0.008,
        0.020,
        default=0.016,
        decimals=3,
        space="sell",
        optimize=False,
    ),
    "pSL_1": DecimalParameter(
        0.008,
        0.020,
        default=0.011,
        decimals=3,
        space="sell",
        optimize=False,
    ),
    # profit threshold 2, SL_2 is used
    "pPF_2": DecimalParameter(
        0.040,
        0.100,
        default=0.080,
        decimals=3,
        space="sell",
        optimize=False,
    ),
    "pSL_2": DecimalParameter(
        0.020,
        0.070,
        default=0.040,
        decimals=3,
        space="sell",
        optimize=False,
    ),
}

SERIES1 = "A_series"
OPERATION = "B_operation"
SERIES2 = "C_series"
