# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IntParameter, DecimalParameter, merge_informative_pair
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame

sys.path.append(str(Path(__file__).parent))

import custom_indicators as cta

# --------------------------------


class BbandRsi2(IStrategy):
    """
    author@: Gert Wohlgemuth

    converted from:

    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs
    """

    # buy_bb_lower = RealParameter(-1.0, 3.0, default=2.0, space='buy')
    buy_rsi = IntParameter(5, 50, default=30, space='buy', load=True)
    buy_inf_pct_adr = DecimalParameter(
        0.70, 0.99, default=0.80, space='buy', load=True, optimize=True
    )
    sell_rsi = IntParameter(50, 100, default=70, space='sell', load=True)

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

    def informative_pairs(self):
        # add all whitelisted pairs on informative timeframe
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.inf_timeframe) for pair in pairs]

        # add extra informative pairs if the stake is BTC or ETH
        if self.config['stake_currency'] in ('BTC', 'ETH'):
            for pair in pairs:
                coin, stake = pair.split('/')
                coin_fiat = f"{coin}/{self.custom_fiat}"
                informative_pairs += [(coin_fiat, self.timeframe)]

            stake_fiat = f"{self.config['stake_currency']}/{self.custom_fiat}"
            informative_pairs += [(stake_fiat, self.timeframe)]
        # if BTC/STAKE is not in whitelist, add it as an informative pair on both timeframes
        else:
            btc_stake = f"BTC/{self.config['stake_currency']}"
            if btc_stake not in pairs:
                informative_pairs += [(btc_stake, self.timeframe)]

        return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        # Base pair informative timeframe indicators
        informative = self.dp.get_pair_dataframe(
            pair=metadata['pair'], timeframe=self.inf_timeframe
        )

        # Get the "average day range" between the 1d high and 1d low to set up guards
        informative['1d-high'] = informative['close'].rolling(24).max()
        informative['1d-low'] = informative['close'].rolling(24).min()
        informative['adr'] = informative['1d-high'] - informative['1d-low']

        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, self.inf_timeframe, ffill=True
        )

        # Other stake specific informative indicators
        # e.g if stake is BTC and current coin is XLM (pair: XLM/BTC)
        if self.config['stake_currency'] in ('BTC', 'ETH'):
            coin, stake = metadata['pair'].split('/')
            fiat = self.custom_fiat
            coin_fiat = f"{coin}/{fiat}"
            stake_fiat = f"{stake}/{fiat}"

            # Informative COIN/FIAT e.g. XLM/USD - Base Timeframe
            coin_fiat_tf = self.dp.get_pair_dataframe(
                pair=coin_fiat, timeframe=self.timeframe
            )
            dataframe[f"{fiat}_rmi"] = cta.RMI(coin_fiat_tf, length=55, mom=5)

            # Informative STAKE/FIAT e.g. BTC/USD - Base Timeframe
            stake_fiat_tf = self.dp.get_pair_dataframe(
                pair=stake_fiat, timeframe=self.timeframe
            )
            dataframe[f"{stake}_rmi"] = cta.RMI(stake_fiat_tf, length=55, mom=5)

        # Informatives for BTC/STAKE if not in whitelist
        else:
            pairs = self.dp.current_whitelist()
            btc_stake = f"BTC/{self.config['stake_currency']}"
            if btc_stake not in pairs:
                self.custom_btc_inf = True
                # BTC/STAKE - Base Timeframe
                btc_stake_tf = self.dp.get_pair_dataframe(
                    pair=btc_stake, timeframe=self.timeframe
                )
                dataframe['BTC_rmi'] = cta.RMI(btc_stake_tf, length=55, mom=5)
                dataframe['BTC_close'] = btc_stake_tf['close']
                dataframe['BTC_kama'] = ta.KAMA(btc_stake_tf, length=144)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # Informative Timeframe Guards
        conditions.append(
            (
                dataframe['close']
                <= dataframe[f"1d-low_{self.inf_timeframe}"]
                + (self.buy_inf_pct_adr.value * dataframe[f"adr_{self.inf_timeframe}"])
            )
        )
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
        dataframe.loc[((dataframe['rsi'] > self.sell_rsi.value)), 'sell'] = 1
        return dataframe
