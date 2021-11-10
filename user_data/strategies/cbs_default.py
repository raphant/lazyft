"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
# --- Do not remove these libs ---
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.enums import SellType
from freqtrade.exchange import timeframe_to_prev_date

from cbs import CbsConfiguration
from cbs.populator import Populator
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy, SellCheckTuple
from pandas import DataFrame
from finta import TA as ta
import pandas_ta
import cbs
from cbs.mapper import Mapper
import logging

logger = logging.getLogger(__name__)
try:
    map_file = Path(__file__).parent.joinpath('cbs.json')
except FileNotFoundError:
    logger.warning('No cbs.json file found.')
else:
    logger.info(f'Using cbs.json file: {map_file}')


class CbsStrategy(IStrategy):
    # Stoploss:
    stoploss = -99

    # ROI table:
    minimal_roi = {"0": 100}

    # endregion
    startup_candle_count = 1
    ticker_interval = '5m'

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        cbs_config = CbsConfiguration(map_file=map_file)
        self.mapper = Mapper(cbs_config)

    def bot_loop_start(self, **kwargs) -> None:
        for pair in self.dp.current_whitelist():
            Populator.prep(self, pair, self.mapper)

    def informative_pairs(self) -> ListPairsWithTimeframes:
        pair_timeframe_tuples = set()
        logger.info(
            f'Found {len(Populator._cached_strategies)} strategies in Populator cache'
        )
        for s in Populator._cached_strategies.values():
            pair_timeframe_tuples.update(s.informative_pairs())
        return list(pair_timeframe_tuples)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = Populator.populate_indicators(
            dataframe, metadata['pair'], self.mapper
        )
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = Populator.buy_trend(dataframe, metadata['pair'], self.mapper)
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = Populator.sell_trend(dataframe, metadata['pair'], self.mapper)
        return dataframe

    def custom_sell(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        return super().custom_sell(
            pair, trade, current_time, current_rate, current_profit
        )
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        # Obtain last available candle. Do not use current_time to look up latest candle, because
        # current_time points to current incomplete candle whose data is not available.
        # last_candle = dataframe.iloc[-1].squeeze()
        # In dry/live runs trade open date will not match candle open date therefore it must be
        # rounded.
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        # Look up trade candle.
        trade_candle = dataframe.loc[dataframe["date"] == trade_date]
        if trade_candle.empty:
            return

        trade_candle = trade_candle.squeeze()
        # check to see if any candle has a sell signal
        for strategy in self.mapper.get_strategies(pair):
            if strategy.strategy_name not in trade.buy_tag:
                continue
            # strategy = self.get_strategy(strategy_name)
            # regular sell signal. this does not cover custom_sells
            if (
                strategy.strategy_name in trade_candle["sell_tag"]
                and strategy.strategy_name in trade.buy_tag
            ):
                return "sell_signal"

    def should_sell(
        self,
        trade: Trade,
        rate: float,
        date: datetime,
        buy: bool,
        sell: bool,
        low: float = None,
        high: float = None,
        force_stoploss: float = 0,
    ) -> SellCheckTuple:
        # load the valid strategies for the pair
        strategies = Populator.load_strategies(self.mapper, trade.pair)
        # go through each strategy and ask if it should sell
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # do not honor the sell signal of a strategy that is not in the buy tag
        if sell:
            buy_strategies = set(trade.buy_tag.split(' ')[1].split(','))
            sell_strategies = set(last_candle['sell_strategies'].split(','))
            # make sure at least 1 sell strategy is in the buy strategies
            if not sell_strategies.intersection(buy_strategies):
                sell = False
            else:
                return SellCheckTuple(
                    SellType.SELL_SIGNAL,
                    f'({trade.pair}) {last_candle["sell_strategies"]}-ss',
                )

        for strategy in strategies:
            if strategy.get_strategy_name() not in trade.buy_tag:
                continue
            sell_check = strategy.should_sell(
                trade, rate, date, buy, sell, low, high, force_stoploss
            )
            if sell_check is not None:
                sell_check.sell_reason = (
                    f'({trade.pair.replace("/", "_")}) '
                    f'{strategy.get_strategy_name()}-'
                    f'{sell_check.sell_reason}'
                )
                return sell_check
        return super().should_sell(
            trade, rate, date, buy, sell, low, high, force_stoploss
        )

    # def confirm_trade_exit(
    #     self,
    #     pair: str,
    #     trade: Trade,
    #     order_type: str,
    #     amount: float,
    #     rate: float,
    #     time_in_force: str,
    #     sell_reason: str,
    #     current_time: datetime,
    #     **kwargs,
    # ) -> bool:
    #     strategies = Populator.load_strategies(self.mapper, trade.pair)
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     # Obtain last available candle. Do not use current_time to look up latest candle, because
    #     # current_time points to current incomplete candle whose data is not available.
    #     # last_candle = dataframe.iloc[-1].squeeze()
    #     # In dry/live runs trade open date will not match candle open date therefore it must be
    #     # rounded.
    #     buy_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
    #     # Look up trade candle.
    #     buy_candle = dataframe.loc[dataframe["date"] == buy_date]
    #     sell_candle = dataframe.iloc[-1].squeeze()
    #     buy_strategies = trade.buy_tag.split(' ')[1].split(',')
    #     sell_strategies = sell_candle["sell_strategies"].split(',')
    #     for strategy in strategies:
    #         if (
    #             strategy.get_strategy_name() not in trade.buy_tag
    #             and strategy.get_strategy_name() in sell_reason
    #         ):
    #             return False
    #
    #     return True
