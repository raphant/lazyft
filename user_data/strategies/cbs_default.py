"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
import logging
from datetime import datetime
from pathlib import Path

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.enums import SellType
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy, SellCheckTuple
from pandas import DataFrame

from cbs import CbsConfiguration
from cbs.mapper import Mapper
from cbs.populator import Populator

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

    def informative_pairs(self) -> ListPairsWithTimeframes:
        pair_timeframe_tuples = set()
        logger.info(f'Found {len(Populator.cached_strategies)} strategies in Populator cache')
        for s in Populator.cached_strategies.values():
            pair_timeframe_tuples.update(s.informative_pairs())
        return list(pair_timeframe_tuples)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        Populator.prep(self, metadata['pair'], self.mapper)
        dataframe = Populator.populate_indicators(dataframe, metadata['pair'], self.mapper)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = Populator.buy_trend(dataframe, metadata['pair'], self.mapper)
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = Populator.sell_trend(dataframe, metadata['pair'], self.mapper)
        return dataframe

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
                # do not honor the should_sell of a strategy that is not in the buy tag
                continue
            sell_check = strategy.should_sell(
                trade, rate, date, buy, sell, low, high, force_stoploss
            )
            if sell_check is not None:
                sell_check.sell_reason = (
                    f'({trade.pair}) '
                    f'{strategy.get_strategy_name()}-'
                    f'{sell_check.sell_reason}'
                )
                return sell_check

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
