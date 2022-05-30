"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
import logging
from datetime import datetime, timedelta
from functools import reduce
from typing import Optional, Union

import talib as ta
from diskcache import Index
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    stoploss_from_open,
)
from freqtrade.strategy.interface import IStrategy
from lazyft.space_handler import SpaceHandler
from pandas import DataFrame
from technical import qtpylib

from lft_rest.rest_strategy import BaseRestStrategy

logger = logging.getLogger(__name__)


class BatsContest(IStrategy):
    sh = SpaceHandler(__file__, disable=__name__ != __qualname__)

    # Stoploss:
    stoploss = -1

    # ROI table:
    # minimal_roi = {"160": 0.1}
    minimal_roi = {"0": 1000}

    timeframe = "4h"
    use_custom_stoploss = True

    custom_cooldowns: dict[str, datetime] = {}

    # region Opt Configuration
    load = True
    optimize_rsi = sh.get_space("rsi")
    optimize_atr_roi = sh.get_space("atr_roi")
    optimize_atr_stoploss = sh.get_space("atr_stoploss")
    optimize_high = sh.get_space("high")
    optimize_custom_stoploss = sh.get_space("custom_stoploss")
    optimize_cooldown = sh.get_space("cooldown")
    optimize_risk_reward_ratio = sh.get_space("risk_reward_ratio")
    # endregion

    # region Opt Parameters
    # atr
    atr_roi_multiplier = DecimalParameter(
        1.0, 4.0, default=2, space="buy", optimize=optimize_atr_roi, load=load
    )
    atr_roi_timeperiod = CategoricalParameter(
        list(range(2, 30 + 1, 2)),
        default=2,
        space="buy",
        optimize=optimize_atr_roi,
        load=load,
    )

    atr_stoploss_multiplier = DecimalParameter(
        1.0, 4.0, default=2, space="sell", optimize=optimize_atr_stoploss, load=load
    )
    atr_stoploss_timeperiod = CategoricalParameter(
        list(range(2, 30 + 1, 2)),
        default=2,
        space="sell",
        optimize=optimize_atr_stoploss,
        load=load,
    )
    rsi_value = IntParameter(
        30, 70, default=50, space="buy", optimize=optimize_rsi, load=load
    )
    rsi_timeperiod = CategoricalParameter(
        list(range(2, 30 + 1, 2)),
        default=30,
        space="buy",
        optimize=optimize_rsi,
        load=load,
    )

    close_high_periods = CategoricalParameter(
        list(range(30, 150 + 1, 3)),
        default=48,
        space="buy",
        optimize=optimize_high,
        load=load,
    )

    use_custom_stoploss_ = CategoricalParameter(
        [True, False],
        default=sh.get_setting("use_custom_stoploss", False),
        space="sell",
        optimize=optimize_custom_stoploss,
        load=load,
    )
    # close_high_periods_inf = CategoricalParameter(
    #     list(range(30, 80 + 1, 3)), default=48, space='buy', optimize=optimize_high, load=load
    # )
    pHSL = DecimalParameter(
        -0.99,
        -0.040,
        default=-0.99,
        decimals=3,
        space="sell",
        optimize=False,
        load=False,
    )
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(
        0.01,
        0.9,
        default=0.176,
        decimals=3,
        space="sell",
        optimize=optimize_custom_stoploss,
        load=True,
    )
    pSL_1 = DecimalParameter(
        0.01,
        0.9,
        default=0.176,
        decimals=3,
        space="sell",
        optimize=optimize_custom_stoploss,
        load=True,
    )

    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(
        0.01,
        0.9,
        default=0.627,
        decimals=3,
        space="sell",
        optimize=optimize_custom_stoploss,
        load=True,
    )
    pSL_2 = DecimalParameter(
        0.01,
        0.9,
        default=0.389,
        decimals=3,
        space="sell",
        optimize=optimize_custom_stoploss,
        load=True,
    )

    loss_cooldown = IntParameter(
        1,
        40,
        default=5,
        space="sell",
        optimize=optimize_cooldown,
        load=False,
    )
    profit_cooldown = IntParameter(
        1,
        40,
        default=20,
        space="sell",
        optimize=optimize_cooldown,
        load=False,
    )

    risk_reward_ratio = DecimalParameter(
        1.0,
        6.0,
        default=3.5,
        decimals=1,
        space="sell",
        optimize=optimize_risk_reward_ratio,
        load=True,
    )
    set_to_break_even_at_profit = DecimalParameter(
        0.5,
        3.0,
        default=1.0,
        decimals=1,
        space="sell",
        optimize=optimize_risk_reward_ratio,
        load=True,
    )

    stoploss_type = CategoricalParameter(
        ["a", "b"],
        default="a",
        space="sell",
        optimize=optimize_custom_stoploss,
        load=load,
    )

    custom_sell_type = CategoricalParameter(
        ["a", "b"],
        default="a",
        space="buy",
        optimize=optimize_atr_roi and optimize_atr_stoploss,
        load=load,
    )
    # endregion
    # buy_params = {
    #     "atr_roi_multiplier": 3.487,
    #     "atr_roi_timeperiod": 26,
    #     "close_high_periods": 48,  # value loaded from strategy
    #     "rsi_timeperiod": 30,  # value loaded from strategy
    #     "rsi_value": 50,  # value loaded from strategy
    # }
    #
    # # Sell hyperspace params:
    # sell_params = {
    #     "atr_stoploss_multiplier": 2.837,
    #     "atr_stoploss_timeperiod": 26,
    #     "pHSL": -0.99,  # value loaded from strategy
    #     "pPF_1": 0.176,  # value loaded from strategy
    #     "pPF_2": 0.627,  # value loaded from strategy
    #     "pSL_1": 0.176,  # value loaded from strategy
    #     "pSL_2": 0.389,  # value loaded from strategy
    # }

    # Buy hyperspace params:
    # buy_params = {
    #     "atr_roi_multiplier": 3.557,
    #     "atr_roi_timeperiod": 8,
    #     "close_high_periods": 68,  # value loaded from strategy
    #     "rsi_value": 50,  # value loaded from strategy
    # }

    # Sell hyperspace params:
    # sell_params = {
    #     "pPF_1": 0.176,
    #     "pPF_2": 0.627,
    #     "pSL_1": 0.176,
    #     "pSL_2": 0.389,
    #     "atr_stoploss_multiplier": 1.411,  # value loaded from strategy
    #     "atr_stoploss_timeperiod": 10,  # value loaded from strategy
    # }

    # buy_params = {
    #     "atr_roi_multiplier": 2.065,
    #     "atr_roi_timeperiod": 12,
    #     "close_high_periods": 68,  # value loaded from strategy
    #     "close_high_periods_inf": 48,  # value loaded from strategy
    #     "rsi_timeperiod": 30,  # value loaded from strategy
    #     "rsi_value": 50,  # value loaded from strategy
    # }
    #
    # # Sell hyperspace params:
    # sell_params = {
    #     "atr_stoploss_multiplier": 3.928,
    #     "atr_stoploss_timeperiod": 2,
    # }

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        if self.is_live_or_dry:
            self.persistence = Index(f"{self.__class__.__name__}_persistence")
        else:
            self.persistence = {}

    # def custom_stoploss(
    #     self,
    #     pair: str,
    #     trade: 'Trade',
    #     current_time: datetime,
    #     current_rate: float,
    #     current_profit: float,
    #     **kwargs,
    # ) -> float:
    #     """
    #     custom_stoploss using a risk/reward ratio
    #     """
    #
    #     result = break_even_sl = takeprofit_sl = -1
    #     custom_info_pair = self.persistence.get(pair)
    #
    #     if custom_info_pair is None:
    #         return self.stoploss
    #
    #     # get the atr stoploss at the time of purchase
    #     initial_sl_abs = custom_info_pair['stoploss']
    #
    #     # calculate initial stoploss at open_date
    #     initial_sl = initial_sl_abs / current_rate - 1
    #
    #     # calculate take profit threshold
    #     # by using the initial risk and multiplying it
    #     risk_distance = trade.open_rate - initial_sl_abs
    #
    #     # reward_distance = risk_distance*self.custom_info['risk_reward_ratio']
    #     # replace with hyperoptable parameter
    #     reward_distance = risk_distance * self.risk_reward_ratio.value
    #
    #     # take_profit tries to lock in profit once price gets over
    #     # risk/reward ratio treshold
    #     take_profit_price_abs = trade.open_rate + reward_distance
    #
    #     # take_profit gets triggerd at this profit
    #     take_profit_pct = take_profit_price_abs / trade.open_rate - 1
    #
    #     # break_even tries to set sl at open_rate+fees (0 loss)
    #     # break_even_profit_distance = risk_distance*self.custom_info['set_to_break_even_at_profit']
    #     # replace with hyperoptable parameter
    #     break_even_profit_distance = risk_distance * self.set_to_break_even_at_profit.value
    #
    #     # break_even gets triggerd at this profit
    #     break_even_profit_pct = (break_even_profit_distance + current_rate) / current_rate - 1
    #
    #     result = initial_sl
    #     if current_profit >= break_even_profit_pct:
    #         break_even_sl = (
    #             trade.open_rate * (1 + trade.fee_open + trade.fee_close) / current_rate
    #         ) - 1
    #         result = break_even_sl
    #
    #     if current_profit >= take_profit_pct:
    #         takeprofit_sl = take_profit_price_abs / current_rate - 1
    #         result = takeprofit_sl
    #
    #     return result

    # # Stoploss:
    # stoploss = -0.203
    #
    # Trailing stop:
    # trailing_stop = True
    # trailing_stop_positive = 0.015
    # trailing_stop_positive_offset = 0.115
    # trailing_only_offset_is_reached = True

    # trailing_stop = True
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.066
    # trailing_only_offset_is_reached = True

    # buy_params = {
    #     "atr_roi_multiplier": 3.557,
    #     "atr_roi_timeperiod": 8,
    #     "close_high_periods": 48,  # value loaded from strategy
    #     "rsi_value": 50,  # value loaded from strategy
    # }

    # Sell hyperspace params:
    # sell_params = {
    #     "atr_stoploss_multiplier": 1.411,
    #     "atr_stoploss_timeperiod": 10,
    # }
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        if self.stoploss_type.value == "a":
            return self.custom_stoploss_a(
                pair, trade, current_time, current_rate, current_profit, **kwargs
            )
        elif self.stoploss_type.value == "b":
            return self.custom_stoploss_b(
                pair, trade, current_time, current_rate, current_profit, **kwargs
            )
        return self.stoploss

    def custom_stoploss_a(
        self,
        pair: str,
        trade: "Trade",
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        if not self.use_custom_stoploss_.value:
            return self.stoploss
        # hard stoploss profit
        hard_stop_loss = self.pHSL.value
        profit_level_1 = self.pPF_1.value
        stoploss_level_1 = self.pSL_1.value
        profit_level_2 = self.pPF_2.value
        stoploss_level_2 = self.pSL_2.value

        # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.

        if current_profit > profit_level_2:
            sl_profit = stoploss_level_2 + (current_profit - profit_level_2)
        elif current_profit > profit_level_1:
            sl_profit = stoploss_level_1 + (
                (current_profit - profit_level_1)
                * (stoploss_level_2 - stoploss_level_1)
                / (profit_level_2 - profit_level_1)
            )
        else:
            sl_profit = hard_stop_loss

        # Only for hyperopt invalid return
        if sl_profit >= current_profit:
            return self.stoploss

        return stoploss_from_open(sl_profit, current_profit)

    def custom_stoploss_b(
        self,
        pair: str,
        trade: "Trade",
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        custom_stoploss using a risk/reward ratio
        """
        if not self.use_custom_stoploss_.value:
            return self.stoploss
        result = break_even_sl = takeprofit_sl = -1
        custom_info_pair = self.persistence.get(pair)

        if custom_info_pair is None:
            return self.stoploss

        # get the atr stoploss at the time of purchase
        initial_sl_abs = custom_info_pair["stoploss"]

        # calculate initial stoploss at open_date
        initial_sl = initial_sl_abs / current_rate - 1

        # calculate take profit threshold
        # by using the initial risk and multiplying it
        risk_distance = trade.open_rate - initial_sl_abs

        # reward_distance = risk_distance*self.custom_info['risk_reward_ratio']
        # replace with hyperoptable parameter
        reward_distance = risk_distance * self.risk_reward_ratio.value

        # take_profit tries to lock in profit once price gets over
        # risk/reward ratio treshold
        take_profit_price_abs = trade.open_rate + reward_distance

        # take_profit gets triggerd at this profit
        take_profit_pct = take_profit_price_abs / trade.open_rate - 1

        # break_even tries to set sl at open_rate+fees (0 loss)
        # break_even_profit_distance = risk_distance*self.custom_info['set_to_break_even_at_profit']
        # replace with hyperoptable parameter
        break_even_profit_distance = (
            risk_distance * self.set_to_break_even_at_profit.value
        )

        # break_even gets triggerd at this profit
        break_even_profit_pct = (
            break_even_profit_distance + current_rate
        ) / current_rate - 1

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

    @property
    def is_live_or_dry(self):
        return self.config["runmode"].value in ("live", "dry_run")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # atr
        for i in self.atr_roi_timeperiod.range:
            dataframe[f"roi_atr_{i}"] = ta.ATR(
                dataframe["high"],
                dataframe["low"],
                dataframe["close"],
                timeperiod=i,
            )
        for i in self.atr_stoploss_timeperiod.range:
            dataframe[f"stoploss_atr_{i}"] = ta.ATR(
                dataframe["high"],
                dataframe["low"],
                dataframe["close"],
                timeperiod=i,
            )

        # rsi
        for i in self.rsi_timeperiod.range:
            dataframe[f"rsi_{i}"] = ta.RSI(dataframe["close"], timeperiod=i)
        # self.close_high_periods.value-period close high
        for val in self.close_high_periods.range:
            dataframe[f"close_high_{val}"] = dataframe["close"].rolling(val).max()
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # if close > N bar high

        conditions.append(
            dataframe["close"]
            == dataframe[f"close_high_{self.close_high_periods.value}"]
        )
        # if self.enable_inf:
        #     conditions.append(
        #         dataframe['close']
        #         == dataframe[f'close_high_{self.close_high_periods_inf.value}_1d']
        #     )

        # rsi > self.rsi_value.value
        conditions.append(
            dataframe[f"rsi_{self.rsi_timeperiod.value}"] >= self.rsi_value.value
        )

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "buy"] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sell"] = 0
        return dataframe

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
        # make sure cooldown period has passed
        if pair in self.custom_cooldowns:
            if current_time < self.custom_cooldowns[pair]:
                logger.debug(f"{pair} cooldown period not over yet")
                return False
            else:
                try:
                    logger.debug(f"{pair} cooldown period over")
                    del self.custom_cooldowns[pair]
                except KeyError:
                    pass

        # get atr of last candle
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        stoploss_atr = rate - (
            self.atr_stoploss_multiplier.value
            * last_candle[f"stoploss_atr_{self.atr_stoploss_timeperiod.value}"]
        )
        roi_atr = rate + (
            self.atr_roi_multiplier.value
            * last_candle[f"roi_atr_{self.atr_roi_timeperiod.value}"]
        )
        # roi_atr = last_candle[f'roi_atr_{self.atr_roi_timeperiod.value}']
        # print(f'{pair} stoploss_atr: {stoploss_atr} roi_atr: {roi_atr}')
        self.persistence[pair] = {"stoploss": stoploss_atr, "roi": roi_atr}
        return True

    def custom_sell_a(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        """
        Calculate stop based on:
            Fixed dollar value ($1,000)
            Y * average true range from entry
            Z * average true range from entry (profit target)
        :param pair:
        :param trade:
        :param current_time:
        :param current_rate:
        :param current_profit:
        :param kwargs:
        :return:
        """
        # get the candle at the open date
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        stoploss_atr = last_candle[f"stoploss_atr_{self.atr_stoploss_timeperiod.value}"]
        roi_atr = last_candle[f"roi_atr_{self.atr_roi_timeperiod.value}"]

        # stoploss_atr = self.persistence[pair]['stoploss_atr']
        # roi_atr = self.persistence[pair]['roi_atr']

        # if price is below atr stoploss from entry (`Trade.open_rate`)
        if current_rate <= (
            trade.open_rate - (stoploss_atr * self.atr_stoploss_multiplier.value)
        ):
            return "atr_stoploss"
        # if price is above atr roi from entry
        if current_rate >= (
            trade.open_rate + (roi_atr * self.atr_roi_multiplier.value)
        ):
            return "atr_roi"
        return None

    def custom_sell_b(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        """
        Calculate stop based on:
            Fixed dollar value ($1,000)
            Y * average true range from entry
            Z * average true range from entry (profit target)
        :param pair:
        :param trade:
        :param current_time:
        :param current_rate:
        :param current_profit:
        :param kwargs:
        :return:
        """
        # get the candle at the open date
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        # stoploss_atr = last_candle[f'stoploss_atr_{self.atr_stoploss_timeperiod.value}']
        roi_atr = last_candle[f"roi_atr_{self.atr_roi_timeperiod.value}"]

        stoploss_atr = self.persistence[pair]["stoploss"]
        roi = self.persistence[pair]["roi"]

        # atr trailing stoploss
        peak_profit = self.persistence[pair].get("peak_profit", 0)
        if current_profit > peak_profit:
            logger.info(f"{pair} new peak profit: {current_profit}")
            new_stoploss = current_rate - (
                self.atr_stoploss_multiplier.value
                * last_candle[f"stoploss_atr_{self.atr_stoploss_timeperiod.value}"]
            )
            self.persistence[pair]["stoploss"] = new_stoploss
            self.persistence[pair]["peak_profit"] = current_profit
        elif not peak_profit and current_profit > 0:
            logger.info(f"{pair} peak profit set: {current_profit}")
            self.persistence[pair]["peak_profit"] = current_profit

        logger.info(
            f"{pair} stoploss_atr: {stoploss_atr} roi_atr: {roi} peak_profit: "
            f"{peak_profit} current_rate: {current_rate} current_profit: {current_profit}"
        )
        if current_rate <= stoploss_atr:
            logger.info(f"{pair} stoploss triggered")
            return "atr_stoploss"

        # roi_atr = self.persistence[pair]['roi_atr']

        # if price is below atr stoploss from entry (`Trade.open_rate`)
        # if current_rate <= (trade.open_rate - (stoploss_atr * self.atr_stoploss_multiplier.value)):
        #     return 'atr_stoploss'
        # if price is above atr roi from entry
        if current_rate >= roi:
            logger.info(f"{pair} roi triggered")
            return "atr_roi"

        return None

    def custom_sell(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        if self.custom_sell_type.value == "a":
            return self.custom_sell_a(
                pair, trade, current_time, current_rate, current_profit, **kwargs
            )
        elif self.custom_sell_type.value == "b":
            return self.custom_sell_b(
                pair, trade, current_time, current_rate, current_profit, **kwargs
            )

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
        try:
            del self.persistence[pair]
        except KeyError:
            pass
        return super().confirm_trade_exit(
            pair,
            trade,
            order_type,
            amount,
            rate,
            time_in_force,
            sell_reason,
            current_time,
            **kwargs,
        )

    def custom_exit_price(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        proposed_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        # If last trade was a loser, wait 5 bars before entering next trade (minimizes
        # whipsaws).
        # If last trade was a winner, wait 20 bars before entering next trade (be patient after
        # wins)
        if current_profit < 0:
            until = current_time + timedelta(
                minutes=self.timeframe_to_minutes * int(self.loss_cooldown.value)
            )
            if not self.is_live_or_dry:
                self.custom_cooldowns[pair] = until
            else:
                self.lock_pair(pair, until=until, reason="Losing trade")
        else:
            until = current_time + timedelta(
                minutes=self.timeframe_to_minutes * int(self.profit_cooldown.value)
            )
            if not self.is_live_or_dry:
                self.custom_cooldowns[pair] = until
            else:
                self.lock_pair(pair, until=until, reason="Winning trade")
        return proposed_rate

    @property
    def timeframe_to_minutes(self) -> int:
        """
        Get the timeframe in minutes.
        1d = 1440
        4h = 240
        :return: int
        """
        import re

        timeframe = self.timeframe
        # timeframe can be: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
        # hours
        if re.search(r"h", timeframe):
            return int(re.sub(r"h", "", timeframe)) * 60
        # days
        if re.search(r"d", timeframe):
            return int(re.sub(r"d", "", timeframe)) * 1440
        # minute
        return int(re.sub(r"m", "", timeframe))


class BatsContestRest(BaseRestStrategy, BatsContest):
    backtest_days = 180
    hyperopt_days = 180
    hyperopt_epochs = 40
    min_avg_profit = 0.01
    min_backtest_trades = 2
    min_hyperopt_trades = 2
    min_win_ratio = 0.40
    request_hyperopt = False
    timeframe_detail = "5m"
