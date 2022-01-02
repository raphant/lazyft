import logging

from indicatormix import misc
from indicatormix.advanced_optimizer import AdvancedOptimizer
from indicatormix.strategy.advanced import IMBaseAdvancedOptimizerStrategy

# --- Do not remove these libs ---

logger = logging.getLogger(__name__)

load = True
if __name__ == '':
    load = False


class IndicatorMixAdvancedOpt(IMBaseAdvancedOptimizerStrategy):

    # region IM Config
    n_buy_conditions_per_group = 0
    n_sell_conditions_per_group = 3
    # endregion
    # region Init Adv Opt
    if __name__ == __qualname__:
        # region Comparisons
        buy_params_normal = [
            'bb_fast__bb_upperband > high',
            'zema_slow_30m__zema >= bb_slow_1h__bb_lowerband',
            'adx_1h__adx crossed_below close_30m',
            'hema_fast_30m__hma < bb_fast_1h__bb_upperband',
            'psar_30m__sar > bb_fast_30m__bb_lowerband',
            'rvi_1h__rvi < keltner_channel_1h__lower',
            't3_slow__T3Average trend_crossed_up t3_slow_30m__T3Average',
            'rsi__rsi >= bb_slow_30m__bb_upperband',
            'keltner_channel_1h__lower >= vwap__vwap',
        ]
        sell_params_normal = []
        # endregion
        ao = AdvancedOptimizer(
            misc.reverse_format_parameters(buy_params_normal, 'buy'),
            misc.reverse_format_parameters(sell_params_normal, 'sell'),
            should_optimize_func_kwargs=False,
            should_optimize_values=True,
            should_optimize_offsets=True,
            should_optimize_custom_stoploss=False,
        )
        use_custom_stoploss = True
        locals().update(ao.create_parameters())
        logger.info('IndicatorMixAdvancedOpt: buy comparisons:\n%s', '\n'.join(buy_params_normal))
        logger.info('IndicatorMixAdvancedOpt: sell comparisons:\n%s', '\n'.join(sell_params_normal))

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
    minimal_roi = {"0": 0.141, "13": 0.088, "70": 0.04, "170": 0}
    stoploss = -0.343
    timeframe = '5m'
    # endregion
    # region Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200
    # endregion
