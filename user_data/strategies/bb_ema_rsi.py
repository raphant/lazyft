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


class BbEmaRsi(IStrategy):

    # region Params
    # endregion
    minimal_roi = {"0": 0.10, "20": 0.05, "64": 0.03, "168": 0}
    stoploss = -0.25

    # Optimal timeframe for the strategy
    timeframe = '5m'
    use_custom_stoploss = False

    custom_fiat = "USD"  # Only relevant if stake is BTC or ETH
    custom_btc_inf = False  # Don't change this.

    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    use_custom_stoploss = False

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
        dataframe['ema'] = ta.EMA(dataframe, 100)

        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lower'] = bollinger['lower']
        dataframe['bb_mid'] = bollinger['mid']
        dataframe['bb_upper'] = bollinger['upper']
        # rsi
        dataframe['rsi'] = ta.RSI(dataframe)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # conditions.append(
        #     (qtpylib.crossed_above(dataframe['bb_upper'], dataframe['ema']))
        # )
        conditions.append((dataframe['bb_upper'] > dataframe['ema']))
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # rsi greater than or equal to 70
        conditions.append(dataframe['rsi'] >= 70)

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe

    # def custom_sell(
    #     self,
    #     pair: str,
    #     trade: Trade,
    #     current_time: datetime,
    #     current_rate: float,
    #     current_profit: float,
    #     **kwargs,
    # ) -> Optional[Union[str, bool]]:
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     last_candle = dataframe.iloc[-1].squeeze()
    #     last_2_candles = dataframe.iloc[-2:-1].squeeze()
    #     time_elapsed = current_time - trade.open_date
    #     if time_elapsed.total_seconds() > 60 * 60:
    #         crossed_above = qtpylib.crossed_above(
    #             last_2_candles['sar'], dataframe['bb_mid']
    #         )
    #         if crossed_above:
    #             return 'adjusted-signal'
    #     else:
    #         crossed_above = qtpylib.crossed_above(
    #             last_2_candles['sar'], dataframe['bb_upper']
    #         )
    #         if crossed_above:
    #             return 'sell-signal'
