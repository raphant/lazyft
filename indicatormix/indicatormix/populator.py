import logging
from typing import Any, TYPE_CHECKING

import numpy as np
from freqtrade.strategy.hyper import BaseParameter, NumericParameter
from pandas import DataFrame, Series

from indicatormix.entities.indicator import Indicator
from indicatormix import State


logger = logging.getLogger(__name__)


class Populator:
    @staticmethod
    def populate(state: State, indicator_name: str, dataframe: DataFrame) -> DataFrame:
        indicator = state.indicator_depot.get(indicator_name)
        func_args = Populator.get_function_arguments(indicator, dataframe)
        func_kwargs = {k: v.value for k, v in indicator.function_kwargs.items()}
        func_result = Populator.execute_function(
            indicator,
            func_args,
            func_kwargs,
        )
        dataframe = Populator.extract_columns_from_func(
            state, indicator, func_result, dataframe
        )
        return dataframe

    @staticmethod
    def populate_with_hyperopt(
        state: State, indicator_name: str, dataframe: DataFrame
    ) -> DataFrame:
        """
        Populate the dataframe with the ranges of each function_parameter's range.
        1. Get args and kwargs from get_func_args_and_kwargs with ranges=True
        2. Run self.func once for each value in the range of each parameter
        """
        indicator = state.indicator_depot.get(indicator_name)
        args = Populator.get_function_arguments(indicator, dataframe)
        kwargs = indicator.function_kwargs
        optimizable_params = [(k, v) for k, v in kwargs.items() if v.optimize]

        assert (
            len(optimizable_params) <= 1
        ), f'Could not populate {indicator.name}. Only one hyperparameter can be optimized at a time'
        # check if any key in kwargs contains a "timeperiod" substring, if not, return Populate.populate
        if not any(map(lambda x: 'timeperiod' in x, kwargs.keys())):
            return Populator.populate(state, indicator_name, dataframe)

        # if there is only one hyperparameter to optimize,
        # we can use the regular function to populate the dataframe
        # if not optimizable_params:
        #     return Populator.populate(state, indicator_name, dataframe)
        if not optimizable_params:
            # grab first parameter regardless of optimization status
            name, parameter = list(kwargs.items())[0]
        else:
            # get the optimizable parameter from kwargs
            name, parameter = optimizable_params[0]

        # go through the ranges of the optimizable parameter and populate using execute_function
        # we will need to pass the kwargs to the function as well, so we need to copy the dict
        # noinspection PyUnresolvedReferences
        for value in parameter.range:
            kwargs = kwargs.copy()
            # the accompanying parameters in kwargs will be of type BaseParameter, we need to
            # set those to their values using parameter.value
            kwargs[name] = value
            for key, p in kwargs.items():
                if isinstance(p, BaseParameter):
                    kwargs[key] = p.value
            func_result = Populator.execute_function(
                indicator,
                args,
                kwargs,
            )
            dataframe = Populator.extract_columns_from_func(
                state, indicator, func_result, dataframe, '_' + str(value)
            )
        return dataframe

    @staticmethod
    def get_function_arguments(indicator: Indicator, dataframe: DataFrame) -> list:
        args = []
        if indicator.func_columns:
            for column in indicator.func_columns:
                args.append(dataframe[column])
        else:
            args.append(dataframe.copy())
        return args

    @staticmethod
    def execute_function(
        indicator: Indicator,
        args: list,
        kwargs: dict,
    ) -> DataFrame:
        try:
            func_result = indicator.func(*args, **kwargs)
        except Exception as e:
            # show debug information
            logger.error(
                f'{indicator.name} failed to run with args: {args} and kwargs: {kwargs}'
            )
            raise e
        return func_result

    @staticmethod
    def extract_columns_from_func(
        state: 'State',
        indicator: Indicator,
        func_result: Any,
        dataframe: DataFrame,
        column_append='',
    ) -> DataFrame:
        if isinstance(func_result, (Series, np.ndarray)):
            col_name = indicator.formatted_columns[0] + column_append
            dataframe.loc[:, col_name] = func_result
            if indicator.informative:
                state.series_to_inf_series_map[col_name] = (
                    col_name + f'_{indicator.timeframe}'
                )
            state.series_map[col_name] = indicator
        elif isinstance(func_result, DataFrame):
            for idx, _ in enumerate(indicator.columns):
                try:
                    col_name = indicator.formatted_columns[idx] + column_append
                    dataframe.loc[:, col_name] = func_result[indicator.columns[idx]]
                    if indicator.informative:
                        state.series_to_inf_series_map[col_name] = (
                            col_name + f'_{indicator.timeframe}'
                        )
                    state.series_map[col_name] = indicator
                except KeyError:
                    # raise error and let the user know what the func_result columns are
                    raise KeyError(
                        f'The function for {indicator.name} returned a DataFrame with the '
                        f'columns {func_result.columns}'
                        f' but the columns {indicator.columns} were expected.'
                    )
        else:
            raise ValueError(
                f'{indicator.name} returned a value of type {type(func_result)}'
                f' which is not supported. Please return a Series or DataFrame.'
            )
        return dataframe
