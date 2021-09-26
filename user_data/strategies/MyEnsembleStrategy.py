import concurrent
import logging
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import reduce
from itertools import combinations
from pathlib import Path
from typing import Optional, Union, Dict

import pandas as pd
import rapidjson
from freqtrade.exchange import timeframe_to_prev_date
from freqtrade.persistence import Trade
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import (
    IStrategy,
)
from freqtrade.strategy.interface import SellCheckTuple
from pandas import DataFrame
from pandas.core.common import SettingWithCopyWarning

warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)
logger = logging.getLogger(__name__)
keys_to_delete = [
    "minimal_roi",
    "stoploss",
    "trailing_stop",
    "trailing_stop_positive_offset",
    "trailing_only_offset_is_reached",
    "use_custom_stoploss",
    "ignore_roi_if_buy_signal",
]

ensemble_path = Path('user_data/strategies/ensemble.json')

STRATEGIES = []
if ensemble_path.exists():
    STRATEGIES = rapidjson.loads(ensemble_path.resolve().read_text())

STRAT_COMBINATIONS = reduce(
    lambda x, y: list(combinations(STRATEGIES, y)) + x, range(len(STRATEGIES) + 1), []
)
# logger.info('\nStrat combinations: %s\n', list(enumerate(STRAT_COMBINATIONS)))

MAX_COMBINATIONS = len(STRAT_COMBINATIONS) - 2


class MyEnsembleStrategy(IStrategy):
    loaded_strategies = {}
    informative_timeframe = "1h"

    stoploss = -0.99  # effectively disabled.
    # sell_profit_offset = (
    #     0.001  # it doesn't meant anything, just to guarantee there is a minimal profit.
    # )
    use_sell_signal = True
    ignore_roi_if_buy_signal = False
    sell_profit_only = False

    # Trailing stoploss
    trailing_stop = False
    trailing_only_offset_is_reached = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = None

    # Custom stoploss
    use_custom_stoploss = False

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    minimal_roi = {"0": 100}

    plot_config = {
        'main_plot': {
            "buy_sell": {
                "sell_tag": {"color": "red"},
                "buy_tag": {"color": "blue"},
            },
        }
    }
    # protections = [
    #     {"method": "CooldownPeriod", "stop_duration_candles": 2},
    #     {
    #         "method": "StoplossGuard",
    #         "lookback_period_candles": 100,
    #         "trade_limit": 4,
    #         "stop_duration_candles": 10,
    #         "only_per_pair": True,
    #     },
    # ]

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        logger.info(f"Buy strategies: {STRATEGIES}")

    def informative_pairs(self):
        inf_pairs = []
        # get inf pairs for all strategies
        for s in STRATEGIES:
            strategy = self.get_strategy(s)
            inf_pairs.extend(strategy.informative_pairs())
        # remove duplicates
        return list(set(inf_pairs))

    def get_strategy(self, strategy_name):
        strategy = self.loaded_strategies.get(strategy_name)
        if not strategy:
            config = self.config.copy()
            config["strategy"] = strategy_name
            for k in keys_to_delete:
                try:
                    del config[k]
                except KeyError:
                    pass
            strategy = StrategyResolver.load_strategy(config)
            strategy.process_only_new_candles = self.process_only_new_candles
            self.loaded_strategies[strategy_name] = strategy

        strategy.dp = self.dp
        strategy.wallets = self.wallets
        return strategy

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # logger.info('Populating indicators for %s', metadata['pair'])

        strategies = STRAT_COMBINATIONS[0]
        inf_frames: list[pd.DataFrame] = []
        for strategy_name in strategies:
            # logger.info('Populating %s', strategy_name)
            strategy = self.get_strategy(strategy_name)
            dataframe = strategy.advise_indicators(dataframe, metadata)
            # remove inf data from dataframe to avoid duplicates
            # _x or _y gets added to the inf columns that already exist
            inf_frames.append(dataframe.filter(regex=r'\w+_\d{1,2}[mhd]'))
            dataframe = dataframe[
                dataframe.columns.drop(
                    list(dataframe.filter(regex=r'\w+_\d{1,2}[mhd]'))
                )
            ]

        # add informative data back to dataframe
        for frame in inf_frames:
            for col, series in frame.iteritems():
                if col in dataframe:
                    continue
                dataframe[col] = series
        return dataframe

    def analyze(self, pairs: list[str]) -> None:
        """used in live"""
        t1 = time.time()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for pair in pairs:
                futures.append(executor.submit(self.analyze_pair, pair))
            for future in concurrent.futures.as_completed(futures):
                future.result()
        # self.average_times.append(time.time() - t1)
        logger.info('Analyzed everything in %.f2 seconds', time.time() - t1)

    def advise_all_indicators(self, data: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        """only used in backtesting"""

        def worker(data_: DataFrame, metadata: dict):
            return {
                'pair': metadata['pair'],
                'data': self.advise_indicators(data_, metadata),
            }

        t1 = time.time()
        new_data = {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for pair, pair_data in data.items():
                futures.append(
                    executor.submit(worker, pair_data.copy(), {'pair': pair})
                )
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                new_data[result['pair']] = result['data']
        # indicators = super().advise_all_indicators(data)
        logger.info('Advise all elapsed: %s', time.time() - t1)
        return new_data

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # logger.info('Populating buy_trend for %s', metadata['pair'])
        strategies = STRATEGIES.copy()
        dataframe['ensemble_buy'] = ''
        for strategy_name in strategies:
            strategy = self.get_strategy(strategy_name)
            strategy_indicators = strategy.advise_buy(dataframe, metadata)
            strategy_indicators['strategy'] = ''
            strategy_indicators.loc[
                strategy_indicators.buy == 1, 'strategy'
            ] = strategy_name

            strategy_indicators['existing_buy'] = dataframe['ensemble_buy']
            strategy_indicators['ensemble_buy'] = strategy_indicators.apply(
                lambda x: concat_strategy(x['strategy'], x['existing_buy']), axis=1
            )
            dataframe['ensemble_buy'] = strategy_indicators['ensemble_buy']
            # dataframe[f"ensemble_buy"] = ["buy"]
        # signals = dataframe.filter(like='strat_buy_signal_')
        # signal_names = '+'.join([s.split('_', 3)[-1] for s in list(signals.keys())])

        dataframe.loc[dataframe.ensemble_buy != '', 'buy'] = 1
        dataframe.loc[dataframe.buy == 1, 'buy_tag'] = dataframe['ensemble_buy']
        dataframe.drop(
            ['ensemble_buy', 'existing_buy', 'strategy'],
            axis=1,
            inplace=True,
            errors='ignore',
        )
        # if not self.buy_example:
        #     logger.info(
        #         'buy slice example of %s: %s',
        #         metadata['pair'],
        #         dataframe.iloc[-1].squeeze(),
        #     )
        #     self.buy_example = True
        # self.average_times.append(time.time() - t1)
        return dataframe

    @property
    def is_live_or_dry(self):
        return self.config['runmode'].value in ('live', 'dry_run')

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # logger.info('Populating sell_trend for %s', metadata['pair'])

        dataframe['ensemble_sell'] = ''
        strategies = STRATEGIES.copy()
        # only populate strategies with open trades
        if self.is_live_or_dry:
            strategies_in_trades = set()
            trades: list[Trade] = Trade.get_open_trades()
            for t in trades:
                strategies_in_trades.update(t.buy_tag.split(','))
            strategies = strategies_in_trades
        for strategy_name in strategies:
            self.get_sell_trend_of_strategy(dataframe, metadata, strategy_name)
            # dataframe[f"ensemble_sell"] = ["sell"]
        # signals = dataframe.filter(like='strat_sell_signal_')
        # signal_names = '+'.join([s.split('_', 3)[-1] for s in list(signals.keys())])

        dataframe.loc[dataframe.ensemble_sell != '', 'sell'] = 1
        dataframe['sell_tag'] = ''
        dataframe.loc[dataframe.sell == 1, 'sell_tag'] = dataframe['ensemble_sell']
        dataframe['sell'] = 0
        dataframe.drop(
            ['ensemble_sell', 'existing_sell', 'strategy'],
            axis=1,
            inplace=True,
            errors='ignore',
        )
        return dataframe

    def get_sell_trend_of_strategy(self, dataframe, metadata, strategy_name):
        strategy = self.get_strategy(strategy_name)
        strategy_indicators = strategy.advise_sell(dataframe, metadata)
        strategy_indicators['strategy'] = ''
        strategy_indicators.loc[
            strategy_indicators.sell == 1, 'strategy'
        ] = strategy_name
        strategy_indicators['existing_sell'] = dataframe['ensemble_sell']
        strategy_indicators['ensemble_sell'] = strategy_indicators.apply(
            lambda x: concat_strategy(x['strategy'], x['existing_sell']), axis=1
        )
        dataframe['ensemble_sell'] = strategy_indicators['ensemble_sell']

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
        return super().should_sell(
            trade, rate, date, buy, sell, low, high, force_stoploss
        )

    # def custom_stoploss(
    #     self,
    #     pair: str,
    #     trade: Trade,
    #     current_time: datetime,
    #     current_rate: float,
    #     current_profit: float,
    #     **kwargs,
    # ) -> float:
    #     """
    #     new custom stoploss, both hard and trailing functions. Trailing stoploss first rises at a slower
    #     rate than the current rate until a profit threshold is reached, after which it rises at a constant
    #     percentage as per a normal trailing stoploss. This allows more margin for pull-backs during a rise.
    #     """
    #
    #     # hard stoploss profit
    #     HSL = self.sell_HSL.value
    #     PF_1 = self.sell_PF_1.value
    #     SL_1 = self.sell_SL_1.value
    #     PF_2 = self.sell_PF_2.value
    #     SL_2 = self.sell_SL_2.value
    #
    #     # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
    #     # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
    #     # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.
    #     if current_profit > PF_2:
    #         sl_profit = SL_2 + (current_profit - PF_2)
    #     elif current_profit > PF_1:
    #         sl_profit = SL_1 + ((current_profit - PF_1) * (SL_2 - SL_1) / (PF_2 - PF_1))
    #     else:
    #         sl_profit = HSL
    #
    #     if current_profit > PF_1:
    #         stoploss = stoploss_from_open(sl_profit, current_profit)
    #     else:
    #         stoploss = stoploss_from_open(HSL, current_profit)
    #
    #     return stoploss or stoploss_from_open(HSL, current_profit) or 1

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
        # Obtain last available candle. Do not use current_time to look up latest candle, because
        # current_time points to current incomplete candle whose data is not available.
        last_candle = dataframe.iloc[-1].squeeze()
        # In dry/live runs trade open date will not match candle open date therefore it must be
        # rounded.
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        # Look up trade candle.
        trade_candle = dataframe.loc[dataframe['date'] == trade_date]
        if trade_candle.empty:
            return

        trade_candle = trade_candle.squeeze()
        for strategy_name in STRATEGIES:
            if strategy_name not in trade.buy_tag:
                continue
            strategy = self.get_strategy(strategy_name)
            # regular sell signal. this does not cover custom_sells
            if (
                strategy_name in trade_candle['sell_tag']
                and strategy_name in trade.buy_tag
            ):
                return strategy_name + '-sell_signal'

            strategy_in_buy_tag = (
                bool(trade_candle['buy_tag'])
                and strategy_name in trade_candle['buy_tag']
            )  # do we currently have a valid buy signal?
            valid_buy_signal = bool(trade_candle['buy']) and strategy_in_buy_tag
            should_sell = strategy.should_sell(
                trade,
                current_rate,
                current_time,
                valid_buy_signal,
                False,
                trade_candle['low'],
                last_candle['high'],
            )  # scan for strategies roi/stoploss/custom_sell
            if should_sell.sell_flag:
                return strategy_name + '-' + should_sell.sell_reason

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        sell_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        for strategy_name in trade.buy_tag.split(','):
            strategy = self.get_strategy(strategy_name)
            try:
                trade_exit = strategy.confirm_trade_exit(
                    pair,
                    trade,
                    order_type,
                    amount,
                    rate,
                    time_in_force,
                    sell_reason,
                    current_time=current_time,
                )
            except Exception as e:
                logger.exception(
                    'Exception from %s in confirm_trade_exit', strategy_name, exc_info=e
                )
                continue
            if not trade_exit:
                return False
        if sell_reason == 'trailing_stop_loss':
            return False
        return True


def concat_strategy(string1, string2):
    """This strategy will apply all the strategies who's buy signal is True"""
    concat = ','.join([string1, string2]).strip(',')
    return concat
