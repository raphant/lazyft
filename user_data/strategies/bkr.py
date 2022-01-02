import logging

# --- Do not remove these libs ---
from datetime import datetime
from functools import reduce

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    merge_informative_pair,
    stoploss_from_open,
)
from freqtrade.strategy.hyper import BaseParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame

from indicatormix import populator, condition_tools, misc
from indicatormix.advanced_optimizer import AdvancedOptimizer

logger = logging.getLogger(__name__)


buy_params_normal = [
    'keltner_channel__lower < bb_fast__bb_lowerband',
    'keltner_channel__upper > bb_fast__bb_upperband',
    'rsi__rsi < none',
]

sell_params_normal = [
    'keltner_channel__lower < bb_fast__bb_lowerband',
    'keltner_channel__upper > bb_fast__bb_upperband',
    'rsi__rsi > none',
]


class Bkr(IStrategy):
    # region config
    n_buy_conditions_per_group = 0
    n_sell_conditions_per_group = 0
    # endregion
    # region Parameters
    if __name__ == __qualname__:
        ao = AdvancedOptimizer(
            misc.reverse_format_parameters(buy_params_normal, 'buy'),
            misc.reverse_format_parameters(sell_params_normal, 'sell'),
            should_optimize_func_kwargs=True,
            should_optimize_values=True,
            should_optimize_offsets=True,
            should_optimize_custom_stoploss=False,
        )
        use_custom_stoploss = True
        # ao.add_comparison_group(buy_params1, 'buy')
        # ao.add_comparison_group(buy_params2, 'buy')
        # ao.add_comparison_group(buy_params3, 'buy')
        locals().update(ao.create_parameters())

    # endregion
    # region Params

    # ROI table:
    minimal_roi = {"0": 0.141, "13": 0.088, "70": 0.04, "170": 0}

    # Stoploss:
    stoploss = -0.343
    # endregion
    timeframe = '5m'

    # Recommended
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = True
    startup_candle_count = 200

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        # if not self.ao.should_optimize_stoploss:
        #     return self.stoploss
        # hard stoploss profit
        hard_stop_loss: float = getattr(self, 'pHSL').value
        profit_factor1: float = getattr(self, 'pPF_1').value
        stoploss_1: float = getattr(self, 'pSL_1').value
        profit_factor2: float = getattr(self, 'pPF_2').value
        stoploss_2: float = getattr(self, 'pSL_2').value

        # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.
        if current_profit > profit_factor2:
            sl_profit = stoploss_2 + (current_profit - profit_factor2)
        elif current_profit > profit_factor1:
            sl_profit = stoploss_1 + (
                (current_profit - profit_factor1)
                * (stoploss_2 - stoploss_1)
                / (profit_factor2 - profit_factor1)
            )
        else:
            sl_profit = hard_stop_loss

        if current_profit > profit_factor1:
            stoploss = stoploss_from_open(sl_profit, current_profit)
        else:
            stoploss = stoploss_from_open(hard_stop_loss, current_profit)
        if stoploss == 0:
            return self.stoploss
        return stoploss

    def informative_pairs(self) -> ListPairsWithTimeframes:
        pairs = self.dp.current_whitelist()
        # get each timeframe from inf_timeframes
        return [
            (pair, timeframe)
            for pair in pairs
            for timeframe in self.ao.state.indicator_depot.inf_timeframes
        ]

    def populate_informative_indicators(self, dataframe: DataFrame, metadata):
        inf_dfs = {}
        for timeframe in self.ao.state.indicator_depot.inf_timeframes:
            inf_dfs[timeframe] = self.dp.get_pair_dataframe(
                pair=metadata['pair'], timeframe=timeframe
            )
        for indicator in self.ao.indicators.values():
            if not indicator.informative:
                continue
            inf_dfs[indicator.timeframe] = populator.populate(
                self.ao.state, indicator.name, inf_dfs[indicator.timeframe]
            )
        for tf, df in inf_dfs.items():
            dataframe = merge_informative_pair(dataframe, df, self.timeframe, tf)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for indicator in self.ao.indicators.values():
            if indicator.informative:
                continue
            try:
                dataframe = populator.populate_with_ranges(self.ao.state, indicator.name, dataframe)
            except Exception as e:
                logger.error(f"Error populating {indicator.name}: {e}")
                raise e
        dataframe = self.populate_informative_indicators(dataframe, metadata)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'buy_tag'] = ''
        local_parameters = {
            k: v for k, v in self.__class__.__dict__.items() if isinstance(v, BaseParameter)
        }
        conditions = self.ao.create_conditions(
            dataframe, local_parameters, 'buy', self.n_buy_conditions_per_group
        )
        if conditions:
            if self.n_buy_conditions_per_group > 0:
                dataframe = condition_tools.label_tags(
                    dataframe, conditions, 'buy_tag', self.n_buy_conditions_per_group
                )
                # replace empty tags with None
                dataframe.loc[reduce(lambda x, y: x | y, conditions), 'buy'] = 1
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        dataframe['buy_tag'] = dataframe['buy_tag'].replace('', None)
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_tag'] = ''
        local_parameters = {
            k: v for k, v in self.__class__.__dict__.items() if isinstance(v, BaseParameter)
        }
        conditions = self.ao.create_conditions(
            dataframe, local_parameters, 'sell', self.n_sell_conditions_per_group
        )

        if conditions:
            if self.n_sell_conditions_per_group > 0:
                dataframe = condition_tools.label_tags(
                    dataframe, conditions, 'exit_tag', self.n_sell_conditions_per_group
                )
                dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1
            # if sell_comparisons_per_group does not equal 1, then any group in the conditions
            # can be True to generate a sell signal
            else:
                dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1
        return dataframe
