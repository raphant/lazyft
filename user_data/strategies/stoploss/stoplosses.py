import inspect
import sys
from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from pathlib import Path
from typing import Type

from freqtrade.exchange import timeframe_to_prev_date, timeframe_to_seconds
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, stoploss_from_open, IStrategy

from strategies.NotAnotherSMAOffsetStrategyHOv3Mod import (
    NotAnotherSMAOffsetStrategyHOv3Mod,
)

sys.path.append(str(Path(__file__).parent))


class BaseStoploss(IStrategy, ABC):
    use_custom_stoploss = True

    @abstractmethod
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        ...

    @classmethod
    def get_stoploss(cls, strategy: Type[IStrategy]):
        return inherit_from(strategy, cls)


def inherit_from(child: Type[IStrategy], parent: Type[BaseStoploss]) -> Type[IStrategy]:
    """https://stackoverflow.com/a/58975308/3404367"""
    # Prepare bases
    child_bases = inspect.getmro(child)
    parent_bases = inspect.getmro(parent)
    bases = (
        tuple([item for item in parent_bases if item not in child_bases]) + child_bases
    )

    # Construct the new return type
    child = type(child.__name__, bases, child.__dict__.copy())

    return child


class BigZ04TSL3Stoploss(BaseStoploss, ABC):
    # trailing stoploss hyperopt parameters
    # hard stoploss profit
    pHSL = DecimalParameter(
        -0.200,
        -0.040,
        default=-0.08,
        decimals=3,
        space='sell',
        optimize=False,
        load=True,
    )
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(
        0.008, 0.020, default=0.016, decimals=3, space='sell', optimize=False, load=True
    )
    pSL_1 = DecimalParameter(
        0.008, 0.020, default=0.011, decimals=3, space='sell', optimize=False, load=True
    )
    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(
        0.040, 0.100, default=0.080, decimals=3, space='sell', optimize=False, load=True
    )
    pSL_2 = DecimalParameter(
        0.020, 0.070, default=0.040, decimals=3, space='sell', optimize=False, load=True
    )

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:

        # hard stoploss profit
        HSL = self.pHSL.value
        PF_1 = self.pPF_1.value
        SL_1 = self.pSL_1.value
        PF_2 = self.pPF_2.value
        SL_2 = self.pSL_2.value

        # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.

        if current_profit > PF_2:
            sl_profit = SL_2 + (current_profit - PF_2)
        elif current_profit > PF_1:
            sl_profit = SL_1 + ((current_profit - PF_1) * (SL_2 - SL_1) / (PF_2 - PF_1))
        else:
            sl_profit = HSL

        if current_profit > PF_1:
            return stoploss_from_open(sl_profit, current_profit)
        return stoploss_from_open(HSL, current_profit)


class NotAnotherSMAOffsetStrategyModHOStoploss(BaseStoploss, ABC):
    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """Stoploss used by `NotAnotherSMAOffsetStrategyModHO`"""

        assert False, "It worked"
        stoploss = self.stoploss
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        if last_candle is None:
            return stoploss

        trade_date = timeframe_to_prev_date(
            self.timeframe,
            trade.open_date_utc
            - timedelta(seconds=timeframe_to_seconds(self.timeframe)),
        )
        trade_candle = dataframe.loc[dataframe["date"] == trade_date]
        if trade_candle.empty:
            return stoploss

        trade_candle = trade_candle.squeeze()

        dur_minutes = (current_time - trade.open_date_utc).seconds // 60

        slippage_ratio = trade.open_rate / trade_candle["close"] - 1
        slippage_ratio = slippage_ratio if slippage_ratio > 0 else 0
        current_profit_comp = current_profit + slippage_ratio

        if current_profit_comp >= self.trailing_stop_positive_offset:
            return self.trailing_stop_positive

        for x in self.minimal_roi:
            dur = int(x)
            roi = self.minimal_roi[x]
            if dur_minutes >= dur and current_profit_comp >= roi:
                return 0.001

        return stoploss


stoploss = NotAnotherSMAOffsetStrategyModHOStoploss.get_stoploss(
    NotAnotherSMAOffsetStrategyHOv3Mod
)
print([stoploss], help(stoploss.custom_stoploss))
