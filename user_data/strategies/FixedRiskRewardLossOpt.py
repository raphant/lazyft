# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from freqtrade.exchange import timeframe_to_prev_date
from pandas import DataFrame
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import (
    stoploss_from_open,
    merge_informative_pair,
    DecimalParameter,
    IntParameter,
    CategoricalParameter,
)
import diskcache

# --------------------------------
# Add your lib to import here
import talib as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime
from freqtrade.persistence import Trade

# from freqtrade.state import RunMode
import logging

logger = logging.getLogger(__name__)


class FixedRiskRewardLossOpt(IStrategy):
    """
    This strategy uses custom_stoploss() to enforce a fixed risk/reward ratio
    by first calculating a dynamic initial stoploss via ATR - last negative peak

    After that, we caculate that initial risk and multiply it with an risk_reward_ratio
    Once this is reached, stoploss is set to it and sell signal is enabled

    Also there is a break even ratio. Once this is reached, the stoploss is adjusted to minimize
    losses by setting it to the buy rate + fees.

    Hyperoptable for:
    ATR multiplier
    risk_reward_ratio
    set_to_break_even_at_profit
    """

    # these paramters now hyperoptable, use a dummy custom_info structure as it's used later
    #    custom_info = {
    #        'risk_reward_ratio': 3.5,
    #        'set_to_break_even_at_profit': 1,
    #    }
    custom_info = {}

    ATR_multiplier = IntParameter(1, 6, default=2, space='sell', optimize=True, load=True)
    risk_reward_ratio = DecimalParameter(
        1.0, 6.0, default=3.5, decimals=1, space='sell', optimize=True, load=True
    )
    set_to_break_even_at_profit = DecimalParameter(
        0.5, 3.0, default=1.0, decimals=1, space='sell', optimize=True, load=True
    )

    use_custom_stoploss = True
    stoploss = -0.9
    minimal_roi = {"0": 1000}
    timeframe = '1h'

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        if self.is_live_or_dry:
            self.persistence = diskcache.Index(f'{self.__class__.__name__}_persistence')
        else:
            self.persistence = {}

    def is_live_or_dry(self):
        return self.config["runmode"].value in ("live", "dry_run")

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        custom_stoploss using a risk/reward ratio
        """

        result = break_even_sl = takeprofit_sl = -1
        custom_info_pair = self.persistence.get(pair)
        if custom_info_pair is not None:
            # need to select the correct column using hyperoptable parameter
            # initial_sl_abs = open_df['stoploss_rate']
            initial_sl_abs = custom_info_pair['stoploss']

            # calculate initial stoploss at open_date
            initial_sl = initial_sl_abs / current_rate - 1

            # calculate take profit treshold
            # by using the initial risk and multiplying it
            risk_distance = trade.open_rate - initial_sl_abs

            # reward_distance = risk_distance*self.custom_info['risk_reward_ratio']
            # reeplace with hyperoptable parameter
            reward_distance = risk_distance * self.risk_reward_ratio.value

            # take_profit tries to lock in profit once price gets over
            # risk/reward ratio treshold
            take_profit_price_abs = trade.open_rate + reward_distance
            # take_profit gets triggerd at this profit
            take_profit_pct = take_profit_price_abs / trade.open_rate - 1

            # break_even tries to set sl at open_rate+fees (0 loss)
            # break_even_profit_distance = risk_distance*self.custom_info['set_to_break_even_at_profit']
            # replace with hyperoptable parameter
            break_even_profit_distance = risk_distance * self.set_to_break_even_at_profit.value

            # break_even gets triggerd at this profit
            break_even_profit_pct = (break_even_profit_distance + current_rate) / current_rate - 1

            result = initial_sl
            if current_profit >= break_even_profit_pct:
                break_even_sl = (
                    trade.open_rate * (1 + trade.fee_open + trade.fee_close) / current_rate
                ) - 1
                result = break_even_sl

            if current_profit >= take_profit_pct:
                takeprofit_sl = take_profit_price_abs / current_rate - 1
                result = takeprofit_sl

        return result

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
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        self.persistence[pair] = {
            'stoploss': last_candle[f'stoploss_rate_{self.ATR_multiplier.value}']
        }
        return True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['atr'] = ta.ATR(dataframe)

        # this creates a single column with a fixed multiplier, but we want multiple columns with different
        # multipliers as populate_indicators() is only called once.
        # dataframe['stoploss_rate'] = dataframe['close']-(dataframe['atr']*2)
        for i in self.ATR_multiplier.range:
            dataframe[f'stoploss_rate_{i}'] = dataframe['close'] - (dataframe['atr'] * i)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Placeholder Strategy: buys when SAR is smaller then candle before
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        # Allways buys
        dataframe.loc[:, 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Placeholder Strategy: does nothing
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """

        # Never sells
        dataframe.loc[:, 'sell'] = 0
        return dataframe
