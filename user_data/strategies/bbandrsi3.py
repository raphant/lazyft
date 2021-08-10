# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IntParameter,
    DecimalParameter,
    merge_informative_pair,
    CategoricalParameter,
)
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame

sys.path.append(str(Path(__file__).parent))

import custom_indicators as cta

# --------------------------------


class BbandRsi3(IStrategy):
    """
    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs
    """

    buy_rsi = IntParameter(5, 50, default=30, load=True)
    sell_use_macd = CategoricalParameter([True, False], default=False, load=True)
    sell_rsi = IntParameter(50, 100, default=70, load=True)

    # region Params
    stoploss = -0.25

    # endregion

    # Optimal timeframe for the strategy
    inf_timeframe = '1h'
    timeframe = '5m'
    use_custom_stoploss = True

    custom_fiat = "USD"  # Only relevant if stake is BTC or ETH
    custom_btc_inf = False  # Don't change this.

    # Recommended
    use_sell_signal = True
    sell_profit_only = True
    ignore_roi_if_buy_signal = True

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        if (
            current_profit < -0.04
            and current_time - timedelta(minutes=35) > trade.open_date_utc
        ):
            return -0.01

        return -0.99

    # def informative_pairs(self):
    #     # add all whitelisted pairs on informative timeframe
    #     pairs = self.dp.current_whitelist()
    #     informative_pairs = [(pair, self.inf_timeframe) for pair in pairs]
    #
    #     # add extra informative pairs if the stake is BTC or ETH
    #     if self.config['stake_currency'] in ('BTC', 'ETH'):
    #         for pair in pairs:
    #             coin, stake = pair.split('/')
    #             coin_fiat = f"{coin}/{self.custom_fiat}"
    #             informative_pairs += [(coin_fiat, self.timeframe)]
    #
    #         stake_fiat = f"{self.config['stake_currency']}/{self.custom_fiat}"
    #         informative_pairs += [(stake_fiat, self.timeframe)]
    #     # if BTC/STAKE is not in whitelist, add it as an informative pair on both timeframes
    #     else:
    #         btc_stake = f"BTC/{self.config['stake_currency']}"
    #         if btc_stake not in pairs:
    #             informative_pairs += [(btc_stake, self.timeframe)]
    #
    #     return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        # region macd
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        # endregion

        # region Bollinger bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        # endregion
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append(
            (
                (dataframe['rsi'] < self.buy_rsi.value)
                & (dataframe['close'] < dataframe['bb_lowerband'])
            )
        )
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # GUARDS AND TRENDS
        if self.sell_use_macd.value:
            conditions.append(dataframe['macd'] < dataframe['macdsignal'])

        conditions.append(dataframe['rsi'] > self.sell_rsi.value)

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe
