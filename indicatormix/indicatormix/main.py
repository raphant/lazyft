import logging

import pandas_datareader.data as web

from indicatormix import State
from indicatormix.indicator_depot import IndicatorDepot
from indicatormix.parameter_tools import ParameterTools
from indicatormix.populator import Populator

logger = logging.getLogger(__name__)


class IndicatorMix:
    def __init__(self) -> None:
        self.state = State(indicator_depot=IndicatorDepot())

    def main(self):
        logger.info("Filling parameter map")
        self.state.parameter_map.update(ParameterTools.get_all_parameters(self.state))

    @property
    def indicators(self):
        return self.state.indicator_depot.indicators


if __name__ == '__main__':
    im = IndicatorMix()
    im.main()
    print(im.state)
    # download AAPL data
    df = web.DataReader('AAPL', 'yahoo', start='2020-09-10', end='2021-09-09')
    # make ohlc columns lowercase
    df.columns = [c.lower() for c in df.columns]
    dataframe = Populator.populate(
        im.state, im.indicators.get('supertrend_fast').name, df
    )
    # print(dataframe.to_markdown())
    print(im.state.series_to_inf_series_map)
    # print(ParameterTools.create_comparison_groups(im.state, 'buy', 3))
