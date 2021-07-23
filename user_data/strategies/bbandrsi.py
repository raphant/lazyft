# --- Do not remove these libs ---

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.strategy import IntParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame


# --------------------------------


class StudyBbandRsi(IStrategy):
    """
    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs
    """

    # buy_bb_lower = RealParameter(-1.0, 3.0, default=2.0, space='buy')
    buy_rsi = IntParameter(5, 50, default=30, space='buy', load=True)

    sell_rsi = IntParameter(50, 100, default=70, space='sell', load=True)

    # region Params
    stoploss = -0.25

    from pathlib import Path
    import sys
    sys.path.append(str(Path(__file__).parent))
    from util import load

    if locals()['__module__'] == locals()['__qualname__']:
        locals().update(load(locals()['__qualname__']))

    # endregion

    # Optimal timeframe for the strategy
    timeframe = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] < self.buy_rsi.value)
                & (dataframe['close'] < dataframe['bb_lowerband'])
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[((dataframe['rsi'] > self.sell_rsi.value)), 'sell'] = 1
        return dataframe
