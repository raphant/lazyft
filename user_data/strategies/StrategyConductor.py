"""Credit for inspiration and original idea goes to https://github.com/joaorafaelm"""
import concurrent
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Dict

import pandas as pd
import rapidjson
from freqtrade.exchange import timeframe_to_prev_date
from freqtrade.persistence import Trade
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    stoploss_from_open,
    CategoricalParameter,
)
from freqtrade.strategy.interface import SellCheckTuple
from pandas import DataFrame

# warnings.filterwarnings(
#     'ignore',
#     'CustomStoploss.*',
# )
# warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)

sys.path.append(str(Path(__file__).parent))

logger = logging.getLogger(__name__)

ensemble_path = Path('user_data/strategies/ensemble.json')

# Loads strategies from ensemble.json. Or you can add them manually
STRATEGIES = []
if ensemble_path.exists():
    STRATEGIES = rapidjson.loads(ensemble_path.resolve().read_text())

keys_to_delete = [
    "minimal_roi",
    "stoploss",
    "ignore_roi_if_buy_signal",
]


class StrategyConductor(IStrategy):
    """Inspiration from"""

    loaded_strategies = {}

    stoploss = -0.31
    minimal_roi = {'0': 0.1669, '19': 0.049, '61': 0.023, '152': 0}

    # sell_profit_offset = (
    #     0.001  # it doesn't meant anything, just to guarantee there is a minimal profit.
    # )
    use_sell_signal = True
    ignore_roi_if_buy_signal = True
    sell_profit_only = False

    # Custom stoploss
    use_custom_stoploss = True

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200
    # region manigold settings
    # roi
    roi_time_interval_scaling = 1.6
    roi_table_step_size = 5
    roi_value_step_scaling = 0.9
    # stoploss
    stoploss_min_value = -0.02
    stoploss_max_value = -0.3
    # trailing
    trailing_stop_positive_min_value = 0.01
    trailing_stop_positive_max_value = 0.08
    trailing_stop_positive_offset_min_value = 0.011
    trailing_stop_positive_offset_max_value = 0.1
    # endregion

    plot_config = {
        'main_plot': {
            "buy_sell": {
                "sell_tag": {"color": "red"},
                "buy_tag": {"color": "blue"},
            },
        }
    }

    use_custom_stoploss_opt = CategoricalParameter(
        [True, False], default=True, space='sell'
    )
    # region trailing stoploss hyperopt parameters
    # hard stoploss profit
    pHSL = DecimalParameter(
        -0.200,
        -0.040,
        default=-0.15,
        decimals=3,
        space='sell',
        optimize=True,
        load=True,
    )
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(
        0.008, 0.020, default=0.016, decimals=3, space='sell', optimize=True, load=True
    )
    pSL_1 = DecimalParameter(
        0.008, 0.020, default=0.014, decimals=3, space='sell', optimize=True, load=True
    )

    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(
        0.040, 0.100, default=0.024, decimals=3, space='sell', optimize=True, load=True
    )
    pSL_2 = DecimalParameter(
        0.020, 0.070, default=0.022, decimals=3, space='sell', optimize=True, load=True
    )
    # endregion
    slippage_protection = {'retries': 3, 'max_slippage': -0.02}

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # self.gui_thread = None
        if not self.is_live_or_dry:
            from manigold_spaces import HyperOpt

            self.HyperOpt = HyperOpt
        logger.info(f"Strategies: {STRATEGIES}")

        if self.is_live_or_dry:
            self.trailing_stop = True
            self.use_custom_stoploss = False
        else:
            self.trailing_stop = False
            self.use_custom_stoploss = True

    @property
    def is_live_or_dry(self):
        return self.config['runmode'].value in ('live', 'dry_run')

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """Custom Trailing Stoploss by Perkmeister"""
        if not self.use_custom_stoploss_opt.value:
            return self.stoploss
        # hard stoploss profit
        hsl = self.pHSL.value
        pf_1 = self.pPF_1.value
        sl_1 = self.pSL_1.value
        pf_2 = self.pPF_2.value
        sl_2 = self.pSL_2.value

        # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.

        if current_profit > pf_2:
            sl_profit = sl_2 + (current_profit - pf_2)
        elif current_profit > pf_1:
            sl_profit = sl_1 + ((current_profit - pf_1) * (sl_2 - sl_1) / (pf_2 - pf_1))
        else:
            sl_profit = hsl

        return stoploss_from_open(sl_profit, current_profit) or self.stoploss

    def informative_pairs(self):
        inf_pairs = []
        # get inf pairs for all strategies
        for s in STRATEGIES:
            strategy = self.get_strategy(s)
            inf_pairs.extend(strategy.informative_pairs())
        # remove duplicates
        return list(set(inf_pairs))

    def get_strategy(self, strategy_name):
        """https://github.com/joaorafaelm/freqtrade-heroku/blob/master/user_data/strategies/EnsembleStrategy.py"""
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
            # Only handle ROI, Trailing, and stoploss in main strategy
            strategy.use_custom_stoploss = False
            strategy.trailing_stop = False
            strategy.stoploss = -0.99
            strategy.trailing_only_offset_is_reached = False
            strategy.process_only_new_candles = self.process_only_new_candles
            self.startup_candle_count = max(
                self.startup_candle_count, strategy.startup_candle_count
            )
            strategy.dp = self.dp
            strategy.wallets = self.wallets
            self.loaded_strategies[strategy_name] = strategy

        return strategy

    def analyze(self, pairs: list[str]) -> None:
        """used in live. You can comment this method out if you don't want this to run
        multi-threaded"""
        # t1 = time.time()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for pair in pairs:
                futures.append(executor.submit(self.analyze_pair, pair))
            for future in concurrent.futures.as_completed(futures):
                future.result()
        # logger.info('Analyzed everything in %f seconds', time.time() - t1)
        # super().analyze(pairs)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        inf_frames: list[pd.DataFrame] = []

        for strategy_name in STRATEGIES:
            strategy = self.get_strategy(strategy_name)
            # essentiall call populate_indicators for each strategy
            dataframe = strategy.advise_indicators(dataframe, metadata)
            # remove informative data from dataframe to avoid duplicates
            # _x or _y gets added to the informative columns that already exist
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

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populates the buy signal for all strategies. Each strategy with a buy signal will be
        added to the buy_tag. Open to constructive criticism!
        """
        strategies = STRATEGIES.copy()
        dataframe.loc[:, 'buy_tag'] = ''
        for strategy_name in strategies:
            # load instance of strategy_name
            strategy = self.get_strategy(strategy_name)
            # essentially call populate_buy_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            strategy_indicators = strategy.advise_buy(dataframe.copy(), metadata)
            # create column for `strategy`
            strategy_indicators.loc[:, 'new_buy_tag'] = ''
            # On every candle that a buy signal is found, strategy_name
            # name will be added to its 'strategy' column
            strategy_indicators.loc[
                strategy_indicators.buy == 1, 'new_buy_tag'
            ] = strategy_name
            # get the strategies that already exist for the row in the original dataframe
            strategy_indicators.loc[:, 'existing_buy_tag'] = dataframe['buy_tag']
            # join the strategies found in the original dataframe's row with the new strategy
            strategy_indicators.loc[:, 'buy_tag'] = strategy_indicators.apply(
                lambda x: ','.join((x['new_buy_tag'], x['existing_buy_tag'])).strip(
                    ','
                ),
                axis=1,
            )
            # update the original dataframe with the new strategies buy signals
            dataframe.loc[:, 'buy_tag'] = strategy_indicators['buy_tag']
        # set `buy` column of rows with a buy_tag to 1
        dataframe.loc[dataframe.buy_tag != '', 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populates the sell signal for all strategies.
        Open to constructive criticism!
        """
        dataframe.loc[:, 'sell_tag'] = ''

        strategies = STRATEGIES.copy()
        # only populate strategies with open trades if live
        if self.is_live_or_dry:
            strategies_in_trades = set()
            trades: list[Trade] = Trade.get_open_trades()
            for t in trades:
                strategies_in_trades.update(t.buy_tag.split(','))
            strategies = strategies_in_trades
        for strategy_name in strategies:
            # load instance of strategy_name
            strategy = self.get_strategy(strategy_name)

            # essentially call populate_sell_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            dataframe_copy = strategy.advise_sell(dataframe.copy(), metadata)

            # create column for `strategy`
            dataframe_copy.loc[:, 'new_sell_tag'] = ''
            # On every candle that a buy signal is found, strategy_name
            # name will be added to its 'strategy' column
            dataframe_copy.loc[dataframe_copy.sell == 1, 'new_sell_tag'] = strategy_name
            # get the strategies that already exist for the row in the original dataframe
            dataframe_copy.loc[:, 'existing_sell_tag'] = dataframe['sell_tag']
            # join the strategies found in the original dataframe's row with the new strategy
            dataframe_copy.loc[:, 'sell_tag'] = dataframe_copy.apply(
                lambda x: ','.join((x['new_sell_tag'], x['existing_sell_tag'])).strip(
                    ','
                ),
                axis=1,
            )
            # update the original dataframe with the new strategies sell signals
            dataframe.loc[:, 'sell_tag'] = dataframe_copy['sell_tag']
            dataframe.loc[dataframe.sell_tag != '', 'sell'] = 1

        # clear sell signals so they can be handled by custom_sell
        # dataframe.loc[:, 'sell'] = 0

        return dataframe

    # def custom_sell(
    #     self,
    #     pair: str,
    #     trade: Trade,
    #     current_time: datetime,
    #     current_rate: float,
    #     current_profit: float,
    #     **kwargs,
    # ) -> Optional[Union[str, bool]]:
    #     """ """
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
    #     # Look up trade candle.
    #     trade_candle = dataframe.loc[dataframe['date'] == trade_date]
    #     if trade_candle.empty:
    #         return
    #     trade_candle = trade_candle.squeeze()
    # check to see if any strategy in the buy_tag has a sell_signal
    # for strategy_name in STRATEGIES:
    #     if strategy_name not in trade.buy_tag:
    #         continue
    #     if (
    #         strategy_name in trade_candle['sell_tag']
    #         and strategy_name in trade.buy_tag
    #     ):
    #         return 'sell_signal'
    #
    # buy_tag = trade_candle['buy_tag']
    # strategy_in_buy_tag = strategy_name in buy_tag
    # valid_buy_signal = bool(trade_candle['buy']) and strategy_in_buy_tag
    # should_sell = strategy.should_sell(
    #     trade,
    #     current_rate,
    #     current_time,
    #     valid_buy_signal,
    #     False,
    #     trade_candle['low'],
    #     last_candle['high'],
    # )  # scan for strategies roi/stoploss/custom_sell
    # if should_sell.sell_flag:
    #     return strategy_name + '-' + should_sell.sell_reason
    # return should_sell.sell_reason

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
        should_sell = super().should_sell(
            trade, rate, date, buy, sell, low, high, force_stoploss
        )
        if should_sell.sell_flag:
            should_sell.sell_reason = trade.buy_tag + '-' + should_sell.sell_reason
        return should_sell

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

        # slippage protection from NotAnotherSMAOffsetStrategy
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        try:
            state = self.slippage_protection['__pair_retries']
        except KeyError:
            state = self.slippage_protection['__pair_retries'] = {}

        candle = dataframe.iloc[-1].squeeze()

        slippage = (rate / candle['close']) - 1
        if slippage < self.slippage_protection['max_slippage']:
            pair_retries = state.get(pair, 0)
            if pair_retries < self.slippage_protection['retries']:
                state[pair] = pair_retries + 1
                return False

        state[pair] = 0
        return True
