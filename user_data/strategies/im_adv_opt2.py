import logging

from indicatormix import misc
from indicatormix.advanced_optimizer import AdvancedOptimizer
from indicatormix.strategy.advanced import IMBaseAdvancedOptimizerStrategy

# --- Do not remove these libs ---

logger = logging.getLogger(__name__)

temp = "supertrend_cross", "crossed"
temp2 = temp
# temp2 = 'psar2', 'sar'


class IndicatorMixAdvancedOpt2(IMBaseAdvancedOptimizerStrategy):
    # region IM Config
    n_buy_conditions_per_group = 3
    n_sell_conditions_per_group = 2
    # endregion
    # region Init Adv Opt
    if __name__ == __qualname__:
        # region Comparisons
        buy_params_normal = [
            f"{temp[0]}__{temp[1]} none none",
        ]
        sell_params_normal = [
            f"{temp2[0]}__{temp2[1]} none none",
        ]
        # endregion
        ao = AdvancedOptimizer(
            misc.reverse_format_parameters(buy_params_normal, "buy"),
            misc.reverse_format_parameters(sell_params_normal, "sell"),
            should_optimize_func_kwargs=True,
            should_optimize_values=False,
            should_optimize_offsets=False,
            should_optimize_custom_stoploss=False,
            should_optimize_trend=False,
        )
        use_custom_stoploss = True
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
    minimal_roi = {"0": 0.201, "12": 0.041, "31": 0.012, "109": 0}
    stoploss = -0.20
    timeframe = "5m"
    # endregion
    # region Recommended
    exit_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200
    # endregion
