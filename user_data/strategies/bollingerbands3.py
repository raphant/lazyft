# --- Do not remove these libs ---
import sys
from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path
from typing import Optional, Union

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

# --------------------------------


class BollingerBands3(IStrategy):
    # buy_rsi = IntParameter(5, 50, default=30, load=True)
    # sell_rsi = IntParameter(50, 100, default=70, load=True)
    buy_low_or_close = CategoricalParameter(
        ['low', 'close', 'high'], default='close', load=True, optimize=True
    )

    sell_band_matching = CategoricalParameter(
        [True, False], default=True, load=True, optimize=True
    )
    # sell_band_matching_offset = DecimalParameter(
    #     low=0.0, high=0.05, default=0.0, load=True
    # )
    sell_low_or_close = CategoricalParameter(
        ['low', 'close', 'high'], default='close', load=True, optimize=True
    )

    # region Params
    stoploss = -0.147
    minimal_roi = {'0': 0.188, '21': 0.095, '35': 0.033, '130': 0}

    # endregion

    # Optimal timeframe for the strategy
    # inf_timeframe = '1h'
    timeframe = '5m'
    use_custom_stoploss = False

    # Recommended
    use_sell_signal = True
    sell_profit_only = True
    ignore_roi_if_buy_signal = True

    # debug
    cust_last_lowerband: dict[str, dict] = {}

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
            (dataframe[self.buy_low_or_close.value] < dataframe['bb_lowerband'])
        )
        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
            # print('last_lowerband:', float(dataframe['bb_lowerband'].tail(1)))
            # print(metadata)
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append(
            (
                qtpylib.crossed_above(
                    dataframe[self.sell_low_or_close.value], dataframe['bb_upperband']
                )
            )
        )
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe

    def custom_sell(
        self,
        pair: str,
        trade: 'Trade',
        current_time: 'datetime',
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if self.sell_band_matching.value and pair in self.cust_last_lowerband:
            cpair = self.cust_last_lowerband.get(pair)
            if trade.open_date not in cpair:
                return
            if cpair[trade.open_date] >= last_candle['bb_upperband']:
                self.cust_last_lowerband[pair].pop(trade.open_date)
                return 'band_matched'

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        """
        Called right before placing a buy order.
        Timing for this function is critical, so avoid doing heavy computations or
        network requests in this method.

        For full documentation please go to https://www.freqtrade.io/en/latest/strategy-advanced/

        When not implemented by a strategy, returns True (always confirming).

        :param pair: Pair that's about to be bought.
        :param order_type: Order type (as configured in order_types). usually limit or market.
        :param amount: Amount in target (quote) currency that's going to be traded.
        :param rate: Rate that's going to be used when using limit orders
        :param time_in_force: Time in force. Defaults to GTC (Good-til-cancelled).
        :param current_time: datetime object, containing the current datetime
        :param **kwargs: Ensure to keep this here so updates to this won't break your strategy.
        :return bool: When True is returned, then the buy-order is placed on the exchange.
            False aborts the process
        """

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        cpair = self.cust_last_lowerband.get(pair, {})
        cpair[current_time] = float(dataframe.loc['']['bb_lowerband'])
        self.cust_last_lowerband[pair] = cpair
        return True

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        sell_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        """
        Called right before placing a regular sell order.
        Timing for this function is critical, so avoid doing heavy computations or
        network requests in this method.
        :return bool: When True is returned, then the sell-order is placed on the exchange.
            False aborts the process
        """

        self.cust_last_lowerband[pair].pop(trade.open_date, None)

        return True
