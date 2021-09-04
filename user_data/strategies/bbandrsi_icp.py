# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path
from typing import Optional, Union, Tuple

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IntParameter, DecimalParameter, merge_informative_pair
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame

sys.path.append(str(Path(__file__).parent))

import custom_indicators as cta

# --------------------------------


class BbandRsi_ICP(IStrategy):
    """
    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs
    """

    buy_rsi = IntParameter(5, 50, default=30, load=True)
    sell_rsi = IntParameter(50, 100, default=70, load=True)

    # region Params
    stoploss = -0.25
    # endregion

    # Optimal timeframe for the strategy
    inf_timeframe = '1h'
    timeframe = '5m'
    use_custom_stoploss = False

    custom_fiat = "USD"  # Only relevant if stake is BTC or ETH
    custom_btc_inf = False  # Don't change this.

    # Recommended
    use_sell_signal = True
    sell_profit_only = True
    ignore_roi_if_buy_signal = True
    coin_profiles = {
        'VRA/USDT': {
            'buy': {'buy_rsi': 41},
            'sell': {'sell_rsi': 50},
            'protection': {},
            'roi': {'0': 0.247, '15': 0.05499999999999999, '75': 0.036, '187': 0},
            'stoploss': {'stoploss': -0.262},
        },
        'HTR/USDT': {
            "buy": {"buy_rsi": 39},
            "sell": {"sell_rsi": 50},
            "protection": {},
            "roi": {"0": 0.08499999999999999, "38": 0.033, "98": 0.018, "186": 0},
            "stoploss": {"stoploss": -0.246},
        },
        'KSM/USDT': {
            'buy': {'buy_rsi': 41},
            'sell': {'sell_rsi': 53},
            'protection': {},
            'roi': {'0': 0.191, '31': 0.024, '90': 0.011, '205': 0},
            'stoploss': {'stoploss': -0.216},
        },
    }

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        if pair not in self.coin_profiles:
            return self.stoploss
        return self.coin_profiles[pair]['stoploss']['stoploss']

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
        trade_dur = int(
            (current_time.timestamp() - trade.open_date_utc.timestamp()) // 60
        )
        _, roi = self.min_roi_reached_entry(trade_dur, trade.pair)
        if roi is None:
            return False
        else:
            return current_profit > roi

    # noinspection PyMethodOverriding
    def min_roi_reached_entry(
        self, trade_dur: int, pair: str
    ) -> Tuple[Optional[int], Optional[float]]:
        roi_list = list(
            filter(
                lambda x: int(x) <= trade_dur, self.coin_profiles[pair]['roi'].keys()
            )
        )
        if not roi_list:
            return None, None
        roi_entry = max(roi_list)
        return roi_entry, self.coin_profiles[pair]['roi'][roi_entry]

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

        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append(
            (
                (
                    dataframe['rsi']
                    < self.coin_profiles[metadata['pair']]['buy']['buy_rsi']
                )
                & (dataframe['close'] < dataframe['bb_lowerband'])
            )
        )
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                dataframe['rsi']
                > self.coin_profiles[metadata['pair']]['sell']['sell_rsi']
            ),
            'sell',
        ] = 1
        return dataframe
