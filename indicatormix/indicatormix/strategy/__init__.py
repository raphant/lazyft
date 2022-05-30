import logging
from abc import ABC
from datetime import datetime
from typing import Callable

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter, merge_informative_pair, stoploss_from_open
from pandas import DataFrame

from indicatormix import State, populator

logger = logging.getLogger(__name__)


class IMBaseStrategy(IStrategy, ABC):
    n_buy_conditions_per_group: int
    n_sell_conditions_per_group: int
    state: State
    populate_func: Callable

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
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
            for timeframe in self.state.indicator_depot.inf_timeframes
        ]

    def populate_informative_indicators(self, dataframe: DataFrame, metadata):
        inf_dfs = {}
        for timeframe in self.state.indicator_depot.inf_timeframes:
            inf_dfs[timeframe] = self.dp.get_pair_dataframe(
                pair=metadata['pair'], timeframe=timeframe
            )
        for indicator in self.state.indicators.values():
            if not indicator.informative:
                continue
            inf_dfs[indicator.timeframe] = populator.populate(
                self.state, indicator.name, inf_dfs[indicator.timeframe]
            )
        for tf, df in inf_dfs.items():
            dataframe = merge_informative_pair(dataframe, df, self.timeframe, tf)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for indicator in self.state.indicators.values():
            if indicator.informative:
                continue
            try:
                dataframe = self.populate_func(self.state, indicator.name, dataframe)
            except Exception as e:
                logger.error(f"Error populating {indicator.name}: {e}")
                raise e
        dataframe = self.populate_informative_indicators(dataframe, metadata)

        return dataframe
