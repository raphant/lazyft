# --- Do not remove these libs ---
import json
import pathlib

from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import RealParameter, IntParameter


# --------------------------------

# ROI table:

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.absolute()
param_file_id = '$NAME'
params_file = pathlib.Path(SCRIPT_DIRECTORY, 'params.json')


def load():
    if '$' in param_file_id or not params_file.exists():
        return {}
    params = json.loads(params_file.read_text())
    return params['StudyAdxSmas'][param_file_id]['params']


class StudyAdxSmas(IStrategy):
    """
    author@: Gert Wohlgemuth
    converted from:
    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/AdxSmas.cs
    """

    buy_adx = IntParameter(5, 50, default=25, space='buy', load=True)

    sell_adx = IntParameter(15, 75, default=25, space='sell', load=True)

    stoploss = -0.25
    locals().update(load())

    # Optimal ticker interval for the strategy
    ticker_interval = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['short'] = ta.SMA(dataframe, timeperiod=3)
        dataframe['long'] = ta.SMA(dataframe, timeperiod=6)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] > self.buy_adx.value)
                & (qtpylib.crossed_above(dataframe['short'], dataframe['long']))
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] < self.sell_adx.value)
                & (qtpylib.crossed_above(dataframe['long'], dataframe['short']))
            ),
            'sell',
        ] = 1
        return dataframe
