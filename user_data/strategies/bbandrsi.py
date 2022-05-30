# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path
from typing import Optional, Tuple, Union

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.strategy.parameters import DecimalParameter, IntParameter
from lazyft.space_handler import SpaceHandler
from pandas import DataFrame

sys.path.append(str(Path(__file__).parent))

import custom_indicators as cta

# --------------------------------


class BbandRsi(IStrategy):
    """
    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs
    """

    sh = SpaceHandler(__file__, disable=__name__ != __qualname__)

    buy_rsi = IntParameter(5, 50, default=30, load=True, optimize=sh.get_space("rsi"))
    sell_rsi = IntParameter(
        50, 100, default=70, load=True, optimize=sh.get_space("rsi")
    )

    buy_bb_sd = IntParameter(1, 4, default=2, load=True, optimize=sh.get_space("bb_sd"))
    sell_bb_sd = IntParameter(
        1, 4, default=2, load=True, optimize=sh.get_space("bb_sd")
    )

    # region Params
    stoploss = -0.10
    # endregion

    # Optimal timeframe for the strategy
    # inf_timeframe = "1h"
    timeframe = "1h"
    use_custom_stoploss = False

    custom_fiat = "USD"  # Only relevant if stake is BTC or ETH
    custom_btc_inf = False  # Don't change this.
    minimal_roi = {"40": 0.0, "30": 0.01, "20": 0.02, "0": 0.04}
    # Recommended
    exit_sell_signal = True
    sell_profit_only = True
    ignore_roi_if_buy_signal = True

    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
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

    def custom_sell(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        return super().custom_sell(
            pair, trade, current_time, current_rate, current_profit, **kwargs
        )

    def min_roi_reached(
        self, trade: Trade, current_profit: float, current_time: datetime
    ) -> bool:
        return super().min_roi_reached(trade, current_profit, current_time)

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
        ohlc = cta.heiken_ashi(dataframe)
        # replace dataframe ohlc data with each series in ohlc
        dataframe = dataframe.assign(**ohlc)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger bands
        # bollinger = qtpylib.bollinger_bands(
        #     qtpylib.typical_price(dataframe), window=20, stds=2
        # )
        # dataframe["bb_lowerband"] = bollinger["lower"]
        # dataframe["bb_middleband"] = bollinger["mid"]
        # dataframe["bb_upperband"] = bollinger["upper"]

        # bolling bands standard deviations
        for i in self.buy_bb_sd.range:
            bollinger = qtpylib.bollinger_bands(
                qtpylib.typical_price(dataframe), window=20, stds=i
            )
            dataframe[f"bb_lowerband_sd{i}"] = bollinger["lower"]
            dataframe[f"bb_middleband_sd{i}"] = bollinger["mid"]
            dataframe[f"bb_upperband_sd{i}"] = bollinger["upper"]
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append(
            (
                (dataframe["rsi"] > self.buy_rsi.value)
                & (
                    dataframe["close"]
                    < dataframe[f"bb_upperband_sd{self.buy_bb_sd.value}"]
                )
            )
        )
        conditions.append(dataframe["volume"].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "buy"] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["rsi"] > self.sell_rsi.value), "sell"] = 1
        return dataframe
