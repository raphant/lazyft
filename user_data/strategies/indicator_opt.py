import logging
import operator
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import reduce
from numbers import Number
from pprint import pprint
from typing import Optional, Union
from itertools import product
import pandas as pd
import talib.abstract as tta
import pandas_ta as pta
import freqtrade.vendor.qtpylib.indicators as qta
from finta import TA as fta
from freqtrade.strategy import CategoricalParameter, IntParameter
from freqtrade.strategy.hyper import BaseParameter
from pandas import DataFrame
from pydantic.dataclasses import dataclass
from rich.console import Console
from skopt.space import Integer

import custom_indicators as ci
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    indicator_dict = yaml.load(open('user_data/strategies/indicators.yml'))
except FileNotFoundError:
    indicator_dict = yaml.load(open('indicators.yml'))

ta_map = {'tta': tta, 'pta': pta, 'qta': qta, 'fta': fta, 'ci': ci}
op_map = {
    # '<': operator.lt,
    # '>': operator.gt,
    # '<=': operator.le,
    # '>=': operator.ge,
    'crossed_above': qta.crossed_above,
    'crossed_below': qta.crossed_below,
}


# partner_map = {
#     'ma': [''],
#     'mom': ['vol'],
#     'trend': [''],
#     'osc': [''],
#     'vol': [''],
# }


def load_function(indicator_name: str) -> Callable:
    lib, func_name = indicator_name.split('.')
    return getattr(ta_map[lib], func_name)


# region models


class CustomParameter(IntParameter):
    def get_space(self, name: str) -> 'Integer':
        logger.critical(
            'Default combo is %s', IndicatorOptHelper.get().combinations[self.value]
        )
        return super().get_space(name)


class FuncField(BaseModel):
    loc: str
    columns: Optional[list[str]] = []
    args: Optional[list] = []
    kwargs: Optional[dict] = {}


class CompareField(BaseModel):
    type: str
    values: list[str] = []


class Indicator(BaseModel):
    func: FuncField
    values: dict = {}
    columns: Optional[list[str]] = []
    compare: CompareField
    sell_op: Optional[str]
    buy_op: Optional[str]
    type: str
    column_append: str = ''
    compare_to: list[str] = Field(default_factory=list)

    @property
    def formatted_columns(self):
        return [c + self.column_append for c in self.columns]

    def populate(self, dataframe: DataFrame):
        func = load_function(self.func.loc)
        columns = self.func.columns
        loaded_args = self.func.args
        kwargs = self.func.kwargs
        args = []
        if columns:
            for c in columns:
                args.append(dataframe[c])
        else:
            args.append(dataframe)
        if loaded_args:
            args.extend(loaded_args)

        func1 = func(*args, **kwargs)
        if isinstance(func1, DataFrame):
            for k in dataframe:
                if k + self.column_append not in dataframe:
                    dataframe[k + self.column_append] = func1[k]
        else:
            dataframe[self.columns[0] + self.column_append] = func1
        return dataframe


class Series(ABC):
    series_name: str

    def get(self, dataframe: DataFrame):
        try:
            return dataframe[self.series_name]
        except Exception as e:
            logger.info('\nseries_name: %s\ndataframe: %s', self.series_name, dataframe)
            logger.exception(e)
            raise


@dataclass(frozen=True)
class IndicatorSeries(Series):
    series_name: str
    indicator_name: str

    @property
    def indicator(self):
        return indicators[self.indicator_name]


@dataclass(frozen=True)
class OhlcSeries(Series):
    series_name: str


@dataclass(frozen=True)
class Comparison(ABC):
    """Abstract"""

    name: str

    @abstractmethod
    def compare(self, dataframe: DataFrame, type_: str) -> bool:
        pass


@dataclass(frozen=True)
class SeriesComparison(Comparison):
    name: str
    series1: IndicatorSeries
    op: str
    series2: Union[IndicatorSeries, OhlcSeries]

    def compare(self, dataframe: DataFrame, *args):
        operation = op_map[self.op]
        series1 = self.series1.get(dataframe)
        series2 = self.series2.get(dataframe)
        return operation(series1, series2)


@dataclass(frozen=True)
class ValueComparison(Comparison):
    name: str
    series1: IndicatorSeries
    op: str
    indicator_name: str

    @property
    def indicator(self):
        return indicators[self.indicator_name]

    def compare(self, dataframe: DataFrame, type_: str):
        operation = op_map[self.op]
        return operation(
            self.series1.get(dataframe),
            self.indicator.values.get(type_),
        )


@dataclass(frozen=True)
class Combination:
    comparisons: list[Comparison]

    # def __repr__(self) -> str:
    #     return ','.join([c.name for c in self.comparisons])


# endregion


class IndicatorOptHelper:
    instance = None

    def __init__(self) -> None:
        self.populated = set()
        self.comparisons: dict[str, Union[SeriesComparison, ValueComparison]] = {
            c.name: c for c in set(self.comparison_permutations())
        }
        self.combinations = self.get_combinations()

    @staticmethod
    def get_types(indicator_type: str):
        ohlc_dict = {
            'open': OhlcSeries(series_name='open'),
            'high': OhlcSeries(series_name='high'),
            'low': OhlcSeries(series_name='low'),
            'close': OhlcSeries(series_name='close'),
        }
        if indicator_type == 'ohlc':
            for v in ohlc_dict.values():
                yield v

        for i, v in indicators.items():
            if v.compare.type == 'series' and indicator_type == v.type:
                for c in v.formatted_columns:
                    yield IndicatorSeries(series_name=c, indicator_name=i)

    def comparison_permutations(self):
        operators = op_map.keys()
        # create (indicator, op, indicator) comparisons
        for indicator1_name, indicator1 in indicators.items():
            if indicator1.compare.type == 'none':
                continue
            for col in indicator1.formatted_columns:
                series1 = IndicatorSeries(
                    series_name=col, indicator_name=indicator1_name
                )
                for op in operators:
                    # check if 'series' in the values of the indicator is True
                    if indicator1.compare.type == 'value':
                        yield ValueComparison(
                            f'{col} {op} value',
                            series1,
                            op,
                            indicator_name=indicator1_name,
                        )
                    elif indicator1.compare.type == 'specific':
                        # go through each specified indicator in indicator1
                        for indicator2_name in indicator1.compare.values:
                            indicator2 = indicators[indicator2_name]
                            # create a comparison for each column series in indicator2
                            for indicator2_col in indicator2.formatted_columns:
                                series2 = IndicatorSeries(
                                    indicator2_col, indicator2_name
                                )
                                yield SeriesComparison(
                                    f'{col} {op} {indicator2_col}',
                                    series1,
                                    op,
                                    series2,
                                )
                    else:  # type is series
                        # go through each specified series type in indicator1 and create a
                        # comparison with series1
                        for series_type in indicator1.compare.values:
                            # get all series of the specified type
                            matched_series = self.get_types(series_type)
                            for series2 in matched_series:
                                # prevent comparing identical indicators
                                if col == series2.series_name:
                                    continue
                                yield SeriesComparison(
                                    f'{col} {op} {series2.series_name}',
                                    series1,
                                    op,
                                    series2,
                                )

    def compare(self, dataframe: DataFrame, comparison: Comparison, type_: str) -> bool:
        logger.info('Comparing %s', comparison.name)
        # # check is series1 has been populated
        # if pair not in comparison.series1.indicator.populated:
        #     dataframe = comparison.series1.indicator.populate(
        #         dataframe, comparison.series1.series_name, pair
        #     )
        # # check if series2 has been populated
        # if (
        #     isinstance(comparison, SeriesComparison)
        #     and isinstance(comparison.series2, IndicatorSeries)
        #     and pair not in comparison.series2.indicator.populated
        # ):
        #     dataframe = comparison.series2.indicator.populate(
        #         dataframe, comparison.series2.series_name, pair
        #     )
        # compare
        return comparison.compare(dataframe, type_)

    def get_combinations(self):
        i = 1
        gen = product(sorted(self.comparisons.values(), key=lambda s: s.name), repeat=3)
        combos = {}
        for c in gen:
            if len(c) == len(set(c)):
                combos[i] = Combination(c)
                i += 1
        # sort starting with the name of the first comparison
        return combos

    def get_parameter(self, type_, default=None):
        logger.info('creating parameter')
        return CustomParameter(
            low=0,
            high=len(self.combinations) - 1,
            default=default or 1,
            space=type_,
        )

    @classmethod
    def get(cls) -> 'IndicatorOptHelper':
        if IndicatorOptHelper.instance:
            return IndicatorOptHelper.instance
        IndicatorOptHelper.instance = cls()
        return IndicatorOptHelper.instance


indicators: dict[str, Indicator] = {
    i: Indicator.parse_obj(v) for i, v in indicator_dict.items()
}
if __name__ == '__main__':
    # print(load_function('tta.ATR'))
    # pprint(
    #     set(
    #         IndicatorOptHelper()
    #         .indicators['ema']
    #         .populate(pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume']))
    #     )
    # )
    # print(load_function('tta.WMA'))
    # Console().print(IndicatorOptHelper().indicators)

    # permutes = IndicatorOptHelper().comparisons
    # permutes_3 = [p for p in list(product(permutes.items(), repeat=2)) if p[0] != p[1]]
    # Console().print(len(permutes), permutes.keys())
    # Console().print(IndicatorOptHelper().get_parameter('buy'))
    # # objects = list(IndicatorOptHelper().get_combinations())
    # # Console().print(objects, len(objects))
    # # print(IndicatorOptHelper().comparisons['WMA < high'])
    # # print(IndicatorOptHelper().combinations[1])
    indicator_helper = IndicatorOptHelper.get()
    combinations = indicator_helper.combinations
    print(len(combinations))
    pprint(combinations[4840067])
    # pprint(IndicatorOptHelper().comparisons)
    ...
