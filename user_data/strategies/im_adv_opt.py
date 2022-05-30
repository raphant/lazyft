import logging
from datetime import datetime
from typing import Optional, Union

import talib.abstract as ta
from freqtrade.persistence import Trade

# --- Do not remove these libs ---
from freqtrade.strategy import CategoricalParameter, DecimalParameter
from lazyft.space_handler import SpaceHandler
from pandas import DataFrame

from indicatormix import misc
from indicatormix.advanced_optimizer import AdvancedOptimizer
from indicatormix.strategy.advanced import IMBaseAdvancedOptimizerStrategy

logger = logging.getLogger(__name__)

load = True
if __name__ == "":
    load = False


class IndicatorMixAdvancedOpt(IMBaseAdvancedOptimizerStrategy):
    sh = SpaceHandler(__file__, disable=__name__ != __qualname__)
    # region IM Config
    n_buy_conditions_per_group = 0
    n_sell_conditions_per_group = 3
    # endregion
    # region Init Adv Opt
    if __name__ == __qualname__:
        # region Comparisons
        buy_params_normal = [
            "stoch__slow_d CDT zema_slow__zema",
            "wma_fast__WMA < t3__T3Average",
        ]
        sell_params_normal = [
            "CDLSHOOTINGSTAR__value <= tema_slow__TEMA",
            "ema_fast__EMA DT keltner_channel__lower",
            "ema_slow__EMA > zema__zema",
        ]
        # endregion
        use_custom_stoploss = sh.get_setting("use_custom_stoploss", False)

        ao = AdvancedOptimizer(
            misc.reverse_format_parameters(buy_params_normal, "buy"),
            misc.reverse_format_parameters(sell_params_normal, "sell"),
            should_optimize_func_kwargs=sh.get_space("func_kwargs"),
            should_optimize_values=sh.get_space("values"),
            should_optimize_offsets=sh.get_space("offsets"),
            should_optimize_custom_stoploss=sh.get_space("custom_stoploss")
            and use_custom_stoploss,
            should_optimize_trend=sh.get_space("trend"),
        )
        locals().update(ao.create_parameters())
        logger.info(
            "IndicatorMixAdvancedOpt: buy comparisons:\n%s",
            "\n".join(buy_params_normal),
        )
        logger.info(
            "IndicatorMixAdvancedOpt: sell comparisons:\n%s",
            "\n".join(sell_params_normal),
        )

    # endregion
    # region Default Params
    # buy_params = {
    #     "atr_1h__offset_low": 0.908,
    #     "bb_fast__offset_low": 0.9,
    #     "bb_fast__timeperiod": 20,
    #     "bb_slow_1h__offset_low": 0.926,
    #     "ema_fast__offset_low": 0.901,
    #     "ema_fast__timeperiod": 9,
    #     "ema_slow__offset_low": 0.982,
    #     "ema_slow__timeperiod": 100,
    #     "hema_fast_1h__offset_low": 0.949,
    #     "rsi__buy": 39,
    #     "rsi__timeperiod": 14,
    #     "sma_fast__offset_low": 0.985,
    #     "sma_fast__timeperiod": 9,
    #     "supertrend_fast__timeperiod": 5,
    #     "vwap__offset_low": 0.911,
    #     "vwap__timeperiod": 10,
    #     "wma_fast_1h__offset_low": 0.908,
    # }
    # sell_params = {
    #     "pHSL": -0.286,
    #     "pPF_1": 0.012,
    #     "pPF_2": 0.062,
    #     "pSL_1": 0.015,
    #     "pSL_2": 0.061,
    #     "atr_1h__offset_high": 0.962,
    #     "bb_fast__offset_high": 1.381,
    #     "bb_slow_1h__offset_high": 1.487,
    #     "ema_fast__offset_high": 0.954,
    #     "ema_slow__offset_high": 1.062,
    #     "hema_fast_1h__offset_high": 1.356,
    #     "rsi__sell": 70,
    #     "sma_fast__offset_high": 1.291,
    #     "vwap__offset_high": 1.362,
    #     "wma_fast_1h__offset_high": 1.391,
    # }
    # minimal_roi = {"0": 0.141, "13": 0.088, "70": 0.04, "170": 0}
    # stoploss = -0.343
    minimal_roi = {"0": 100}
    stoploss = -1

    timeframe = sh.get_setting("timeframe", "2h")
    # endregion
    # region Recommended
    exit_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    # endregion

    # region Stoploss and Target Parameters
    atr_roi_multiplier = DecimalParameter(
        0.5,
        4.0,
        default=1,
        space="buy",
        optimize=sh.get_space("optimize_atr_roi"),
        load=True,
    )
    atr_roi_timeperiod = CategoricalParameter(
        list(range(2, 30 + 1, 2)),
        default=14,
        space="buy",
        optimize=sh.get_space("optimize_atr_roi"),
        load=True,
    )

    atr_stoploss_multiplier = DecimalParameter(
        0.5,
        4.0,
        default=1.5,
        space="sell",
        optimize=sh.get_space("optimize_atr_stoploss"),
        load=True,
    )
    atr_stoploss_timeperiod = CategoricalParameter(
        list(range(2, 30 + 1, 2)),
        default=14,
        space="sell",
        optimize=sh.get_space("optimize_atr_stoploss"),
        load=True,
    )

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
        indicators["atr_roi"] = ta.ATR(
            dataframe["high"],
            dataframe["low"],
            dataframe["close"],
            timeperiod=self.atr_roi_timeperiod.value,
        )
        indicators["atr_stoploss"] = ta.ATR(
            dataframe["high"],
            dataframe["low"],
            dataframe["close"],
            timeperiod=self.atr_stoploss_timeperiod.value,
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
        atr_roi = last_candle["atr_roi"]
        atr_stoploss = last_candle["atr_stoploss"]
        if current_rate >= trade.open_rate + atr_roi * self.atr_roi_multiplier.value:
            return "atr_roi"

        if current_rate <= trade.open_rate - (
            atr_stoploss * self.atr_stoploss_multiplier.value
        ):
            return "atr_stoploss"
