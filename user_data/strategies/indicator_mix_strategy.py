import logging

from indicatormix import parameter_tools
from indicatormix.main import IndicatorMix
from indicatormix.strategy.normal import IMBaseNormalOptimizationStrategy

# --- Do not remove these libs ---

logger = logging.getLogger(__name__)


class IndicatorMixStrategy(IMBaseNormalOptimizationStrategy):
    # region Defaults
    # endregion
    # region IM Config
    num_of_buy_conditions = 6
    num_of_sell_conditions = 3

    n_buy_conditions_per_group = 3
    n_sell_conditions_per_group = 0
    # endregion
    # region Init IM
    if __name__ == __qualname__:
        im = IndicatorMix()
        buy_comparisons, sell_comparisons = parameter_tools.create_local_parameters(
            im.state,
            locals(),
            num_buy=num_of_buy_conditions,
            num_sell=num_of_sell_conditions,
            # buy_skip_comparisons=list(range(1, 2 + 1)),
        )
        # im.add_custom_parameter_values(
        # )
    # endregion
    # region Params
    minimal_roi = {"0": 0.201, "12": 0.041, "31": 0.012, "109": 0}
    stoploss = -0.20
    timeframe = "5m"
    use_custom_stoploss = False

    exit_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = False
    startup_candle_count = 200
    # endregion
