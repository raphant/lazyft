from __future__ import annotations

import logging
from typing import Union

from indicatormix import State, populator
from indicatormix.entities import comparison
from indicatormix.helpers.custom_indicators import macd_strategy

logger = logging.getLogger(__name__)


class IndicatorMix:
    """
    The IndicatorMix class is a class that adds the ability to create a list of indicators
    """
    def __init__(self, timeframe: str = None) -> None:
        self.state = State(timeframe=timeframe)

    @property
    def indicators(self):
        """
        Return the indicators of the depot
        :return: A list of indicators.
        """
        return self.state.indicator_depot.indicators

    def add_custom_parameter_values(self, parameter_values: dict[str, Union[int, float]]):
        """
        Add the given dictionary of parameter values to the custom parameter values of the current state

        :param parameter_values: dict[str, Union[int, float]]
        :type parameter_values: dict[str, Union[int, float]]
        """
        self.state.custom_parameter_values.update(parameter_values)


if __name__ == '__main__':
    import pandas_datareader.data as web

    im = IndicatorMix()
    print(im.state)
    # download AAPL data
    df = web.DataReader('TSLA', 'yahoo', start='2021-09-1')
    # make ohlc columns lowercase
    df.columns = [c.lower() for c in df.columns]
    print(macd_strategy(df['close'], 3, 9, 10))
    exit()
    # print(df.close)
    # print(normalize(df.close))
    dataframe = populator.populate(im.state, 'wavetrend', df)
    print(dataframe.to_markdown())
    # print(dataframe.head().to_markdown())
    # print(dataframe.tail().to_markdown())
    # # print(im.state.series_to_inf_series_map)
    compare = comparison.create(im.state, 'wavetrend__signal', 'none', 'none').compare(
        im.state, dataframe, 'buy'
    )
    # print(compare)
    # print(compare.unique())
    print(compare.sort_values())
