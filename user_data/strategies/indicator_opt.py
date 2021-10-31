import logging
import operator
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Optional, Union

import freqtrade.vendor.qtpylib.indicators as qta
import pandas_ta as pta
import talib.abstract as tta
from finta import TA as fta
from freqtrade.strategy import CategoricalParameter
from pandas import DataFrame
from pydantic.dataclasses import dataclass

try:
    import custom_indicators as ci
except:
    import lazyft.custom_indicators as ci
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


ta_map = {'tta': tta, 'pta': pta, 'qta': qta, 'fta': fta, 'ci': ci}
op_map = {
    '<': operator.lt,
    '>': operator.gt,
    '<=': operator.le,
    '>=': operator.ge,
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


class InvalidSeriesError(Exception):
    pass


# region models


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
    # sell_op: Optional[str]
    # buy_op: Optional[str]
    type: str
    column_append: str = ''
    compare_to: list[str] = Field(default_factory=list)
    inf_timeframes: list[str] = Field(default_factory=list)

    @property
    def formatted_columns(self):
        return [c + self.column_append for c in self.columns]

    @property
    def all_columns(self):
        indicator_list = self.formatted_columns
        for column in self.formatted_columns:
            # combine each column with each value in indicator.inf_timeframes
            for inf_timeframe in self.inf_timeframes:
                indicator_list.append(f'{column}_{inf_timeframe}')
        return indicator_list

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

        result = func(*args, **kwargs)
        if isinstance(result, DataFrame):
            for k in result:
                if k + self.column_append not in dataframe:
                    dataframe[k + self.column_append] = result[k]
        else:
            dataframe[self.formatted_columns[0]] = result
        return dataframe


class IndicatorTools:
    """
    Class to contain indicator functions
    """

    indicator_ids = dict()

    @staticmethod
    def load_indicators():
        """
        Load indicators from file
        """
        indicators_ = {}
        try:
            load_indicators = yaml.load(open('user_data/strategies/indicators.yml'))
        except FileNotFoundError:
            load_indicators = yaml.load(open('indicators.yml'))

        for indicator_name, indicator_dict in load_indicators.items():
            # make sure each indicator has an ID
            indicators_[indicator_name] = Indicator(**indicator_dict)
        return indicators_

    @staticmethod
    def get_max_columns():
        """
        Get the maximum number of columns for any indicator
        """
        n_columns_list = [len(indicator.columns) for indicator in indicators.values()]
        return max(n_columns_list)

    @staticmethod
    def get_max_compare_series():
        """
        Get the maximum number of series for any indicator
        """
        len_series = [
            len(indicator.compare.values) for indicator in indicators.values()
        ]
        return max(len_series)

    @staticmethod
    def get_non_value_type_series():
        """
        Get the non value type series
        """
        non_value_type_indicators = []
        for indicator in indicators.values():
            if indicator.compare.type != 'value':
                non_value_type_indicators.append(indicator)
        # get each column from each non value type series
        non_value_type_columns = [
            [c for c in indicator.all_columns]
            for indicator in non_value_type_indicators
        ]
        # flatten non value type columns
        non_value_type_columns = [
            column for sublist in non_value_type_columns for column in sublist
        ]
        return list(set(non_value_type_columns))

    @classmethod
    def get_all_indicators(cls):
        indicator_list = set()
        # combine all indicator.proper_columns with each inf_timeframe
        # iterate through all indicators
        for indicator in indicators.values():
            # iterate through all formatted_columns
            indicator_list.update(indicator.all_columns)
        return list(indicator_list)

    @classmethod
    def create_series_indicator_map(cls):
        # create a map of series to indicator
        series_indicator_map = {}
        for indicator in indicators.values():
            for column in indicator.all_columns:
                series_indicator_map[column] = indicator
        return series_indicator_map


class Series(ABC):
    series_name: str

    def get(self, dataframe: DataFrame):
        try:
            return dataframe[self.series_name]
        except Exception as e:
            logger.info('\nseries_name: %s\ndataframe: %s', self.series_name, dataframe)
            logger.exception(e)
            raise

    @property
    def name(self):
        return self.series_name


@dataclass(frozen=True)
class IndicatorSeries(Series):
    series_name: str

    @property
    def indicator(self):
        return series_map[self.series_name]


@dataclass(frozen=True)
class OhlcSeries(Series):
    series_name: str


@dataclass(frozen=True)
class Comparison(ABC):
    """Abstract"""

    @abstractmethod
    def compare(self, dataframe: DataFrame, type_: str) -> bool:
        pass

    @classmethod
    def create(
        cls,
        series_name: str,
        op_str: str,
        comparison_series_name: str,
    ) -> Optional['Comparison']:
        """
        Create a comparison object from the parameters in the strategy during hyperopt
        """
        if series_name == 'none':
            raise InvalidSeriesError()
        indicator = series_map[series_name]
        if indicator.compare.type == 'none':
            raise InvalidSeriesError()
        series1 = IndicatorSeries(series_name)
        # return comparison based on the compare type
        if series_name == 'none':
            raise InvalidSeriesError()
        if indicator.compare.type == 'value':
            return ValueComparison(series1, op_str)
        else:
            if indicator.compare.type == 'specific':
                # if there is more than on value in indicator.compare.values and the comparison
                # series is not in the list of values, raise invalid
                if (
                    len(indicator.compare.values) > 1
                    and comparison_series_name not in indicator.compare.values
                ):
                    raise InvalidSeriesError()
                # set the comparison series name to the first indicator.compare.values
                comparison_series_name = indicator.compare.values[0]
            # create OhlcSeries if the comparison series is in ohlc
            if comparison_series_name in ['open', 'high', 'low', 'close']:
                comparison_series = OhlcSeries(comparison_series_name)
            else:
                comparison_series = IndicatorSeries(comparison_series_name)
            return SeriesComparison(series1, op_str, comparison_series)


@dataclass(frozen=True)
class SeriesComparison(Comparison):
    series1: IndicatorSeries
    op: str
    series2: Union[IndicatorSeries, OhlcSeries]

    def compare(self, dataframe: DataFrame, *args):
        series1 = self.series1.get(dataframe)
        operation = op_map[self.op]
        series2 = self.series2.get(dataframe)
        return operation(series1, series2)

    @property
    def name(self):
        return f'{self.series1.series_name} {self.op} {self.series2.name}'


@dataclass(frozen=True)
class ValueComparison(Comparison):
    series1: IndicatorSeries
    op: str

    @property
    def indicator(self):
        return series_map[self.series1.series_name]

    def compare(self, dataframe: DataFrame, type_: str):
        operation = op_map[self.op]
        return operation(
            self.series1.get(dataframe),
            self.indicator.values.get(type_),
        )

    @property
    def name(self):
        return f'{self.series1.series_name} {self.op}'

    # def __repr__(self) -> str:
    #     return ','.join([c.name for c in self.comparisons])


# endregion


class IndicatorOptHelper:
    instance = None

    def __init__(self, n_permutations: int) -> None:
        self.populated = set()
        self.n_permutations = n_permutations

    @property
    def inf_timeframes(self):
        # create inf_timeframes from all indicators
        timeframes = set()
        for indicator in indicators.values():
            timeframes.update(indicator.inf_timeframes)
        return timeframes

    @staticmethod
    def compare(dataframe: DataFrame, comparison: Comparison, type_: str) -> bool:
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

    def create_parameters(self, type_, permutations: int = None):
        logger.info('creating group parameters')

        comparison_groups = {}

        all_indicators = IndicatorTools.get_all_indicators() + ['none']
        series = IndicatorTools.get_non_value_type_series() + [
            'open',
            'close',
            'high',
            'low',
        ]
        for i in range(1, (permutations or self.n_permutations) + 1):
            group = {
                'series': CategoricalParameter(
                    all_indicators,
                    default=all_indicators[0],
                    space=type_,
                ),
                'operator': CategoricalParameter(
                    list(op_map.keys()), default=list(op_map.keys())[0], space=type_
                ),
                'comparison_series': CategoricalParameter(
                    series,
                    default=series[0],
                    space=type_,
                ),
            }
            comparison_groups[i] = group
        return comparison_groups

    @classmethod
    def get(cls, permutations=2) -> 'IndicatorOptHelper':
        if IndicatorOptHelper.instance:
            return IndicatorOptHelper.instance
        IndicatorOptHelper.instance = cls(permutations)
        return IndicatorOptHelper.instance


indicators = IndicatorTools.load_indicators()
series_map = IndicatorTools.create_series_indicator_map()
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
    # indicator_helper = IndicatorOptHelper.get()
    # combinations = indicator_helper.combinations
    # print(len(combinations))
    # pprint(combinations[4818325])
    # pprint(IndicatorOptHelper().comparisons)
    print(IndicatorTools.get_all_indicators())
    print(IndicatorTools.get_non_value_type_series())
    # pprint(IndicatorOptHelper.get().create_parameters('buy'))
    ...
