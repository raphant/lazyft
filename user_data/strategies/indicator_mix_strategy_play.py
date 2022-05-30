from datetime import datetime
from typing import Optional, Union

import talib as ta
from freqtrade.persistence import Trade
from lazyft.space_handler import SpaceHandler
from pandas import DataFrame

from indicatormix import misc, parameter_tools
from indicatormix.main import IndicatorMix
from indicatormix.strategy.normal import IMBaseNormalOptimizationStrategy

load = True
if __name__ == "":
    load = False

buy_params_normal = [
    "sma_fast__SMA <= bb_fast__bb_upperband",
    "rsi__rsi < none",
    # 'aroon_value__aroon < none',
]
sell_params_normal = [
    "ema_slow_30m__EMA <= ema_slow__EMA",
    "bb_fast_30m__bb_upperband > bb_fast__bb_lowerband",
    "ema_fast__EMA >= open",
    "supertrend_fast__supertrend < none",
    "bb_fast_1h__bb_middleband crossed_below vwap__vwap",
    "bb_slow_1h__bb_lowerband <= hema_fast_1h__hma",
]


class ImsPlay(IMBaseNormalOptimizationStrategy):
    sh = SpaceHandler(__file__, disable=__name__ != __qualname__)

    # region Defaults
    buy_params = misc.reverse_format_parameters(buy_params_normal, "buy")
    sell_params = misc.reverse_format_parameters(sell_params_normal, "sell")
    # endregion
    # region IM Config
    n_buy_conditions_per_group = 0
    n_sell_conditions_per_group = 3

    # num_of_buy_conditions = int(len(buy_params) / 3)
    num_of_buy_conditions = 3
    num_of_sell_conditions = 3

    for i in range(1, num_of_buy_conditions + 1):
        sh.attempted_loads.add(f"buy_condition_{i}")
    for i in range(1, num_of_sell_conditions + 1):
        sh.attempted_loads.add(f"sell_condition_{i}")
    skip_buy_conditions = []
    skip_sell_conditions = []
    for i in range(1, num_of_buy_conditions + 1):
        if sh.get_space(f"buy_condition_{i}") is False:
            skip_buy_conditions.append(i)
    for i in range(1, num_of_sell_conditions + 1):
        if sh.get_space(f"sell_condition_{i}") is False:
            skip_sell_conditions.append(i)
    # endregion
    # region Init IM
    if load:
        im = IndicatorMix(timeframe=sh.get_setting("timeframe"))
        buy_comparisons, sell_comparisons = parameter_tools.create_local_parameters(
            im.state,
            locals(),
            num_buy=num_of_buy_conditions,
            num_sell=num_of_sell_conditions,
            buy_skip_comparisons=skip_buy_conditions,
            sell_skip_comparisons=skip_sell_conditions,
        )
        # im.add_custom_parameter_values(
        #     {
        #         "atr_1h__offset_low": 0.908,
        #         "bb_fast__offset_low": 0.9,
        #         "bb_fast__timeperiod": 20,
        #         "bb_slow_1h__offset_low": 0.926,
        #         "ema_fast__offset_low": 0.901,
        #         "ema_fast__timeperiod": 9,
        #         "ema_slow__offset_low": 0.982,
        #         "ema_slow__timeperiod": 100,
        #         "hema_fast_1h__offset_low": 0.949,
        #         "rsi__buy": 39,
        #         "rsi__timeperiod": 14,
        #         "sma_fast__offset_low": 0.985,
        #         "sma_fast__timeperiod": 9,
        #         "supertrend_fast__timeperiod": 5,
        #         "vwap__offset_low": 0.911,
        #         "vwap__timeperiod": 10,
        #         "wma_fast_1h__offset_low": 0.908,
        #         "pHSL": -0.286,
        #         "pPF_1": 0.012,
        #         "pPF_2": 0.062,
        #         "pSL_1": 0.015,
        #         "pSL_2": 0.061,
        #         "atr_1h__offset_high": 0.962,
        #         "bb_fast__offset_high": 1.381,
        #         "bb_slow_1h__offset_high": 1.487,
        #         "ema_fast__offset_high": 0.954,
        #         "ema_slow__offset_high": 1.062,
        #         "hema_fast_1h__offset_high": 1.356,
        #         "rsi__sell": 70,
        #         "sma_fast__offset_high": 1.291,
        #         "vwap__offset_high": 1.362,
        #         "wma_fast_1h__offset_high": 1.391,
        #     }
        # )
    # endregion
    # region Params
    # minimal_roi = {"0": 0.141, "13": 0.088, "70": 0.04, "170": 0}
    minimal_roi = {"0": 100}

    # Stoploss:
    stoploss = -1
    # timeframe = '5m'
    use_custom_stoploss = False

    exit_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = False
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        It adds the ATR indicator to the indicators dictionary.

        :param dataframe: The dataframe to populate with indicators
        :type dataframe: DataFrame
        :param metadata: dict
        :type metadata: dict
        :return: A DataFrame with the indicators added.
        """
        indicators = super().populate_indicators(dataframe, metadata)
        # add ATR
        indicators["atr"] = ta.ATR(
            dataframe["high"],
            dataframe["low"],
            dataframe["close"],
            timeperiod=20,
        )
        return indicators

    def custom_sell(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        atr = last_candle["atr"]
        if current_rate >= trade.open_rate + atr:
            return "atr_roi"

        if current_rate <= trade.open_rate - (atr * 1.5):
            return "atr_stoploss"
