"""Inspired by EnsembleStrategy from https://github.com/joaorafaelm/freqtrade-heroku/"""

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

ensemble_path = Path("user_data/strategies/ensemble.json")

# Loads strategies from ensemble.json. Or you can add them manually
STRATEGIES = []
if not STRATEGIES and ensemble_path.exists():
    STRATEGIES = rapidjson.loads(ensemble_path.resolve().read_text())

# raise an exception if no strategies are in the list
if not STRATEGIES:
    raise ValueError("No strategies added to strategy list")


keys_to_delete = [
    "minimal_roi",
    "stoploss",
    "ignore_roi_if_buy_signal",
]


class ConductorStrategy(IStrategy):
    """Inspired by EnsembleStrategy from https://github.com/joaorafaelm/freqtrade-heroku/"""

    loaded_strategies = {}

    # feel free to experiment
    stoploss = -0.31
    minimal_roi = {"0": 0.1669, "19": 0.049, "61": 0.023, "152": 0}

    # sell_profit_offset = (
    #     0.001  # it doesn't meant anything, just to guarantee there is a minimal profit.
    # )
    use_sell_signal = True
    ignore_roi_if_buy_signal = True
    sell_profit_only = False

    # Custom stoploss
    use_custom_stoploss = True

    # Run "populate_indicators()" only for new candles.
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
        "main_plot": {
            "buy_sell": {
                "sell_tag": {"color": "red"},
                "buy_tag": {"color": "blue"},
            },
        }
    }

    use_custom_stoploss_opt = CategoricalParameter(
        [True, False], default=False, space="buy"
    )
    # region trailing stoploss hyperopt parameters
    # hard stoploss profit
    pHSL = DecimalParameter(
        -0.200,
        -0.040,
        default=-0.15,
        decimals=3,
        space="sell",
        optimize=True,
        load=True,
    )
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(
        0.008, 0.020, default=0.016, decimals=3, space="sell", optimize=True, load=True
    )
    pSL_1 = DecimalParameter(
        0.008, 0.020, default=0.014, decimals=3, space="sell", optimize=True, load=True
    )

    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(
        0.040, 0.100, default=0.024, decimals=3, space="sell", optimize=True, load=True
    )
    pSL_2 = DecimalParameter(
        0.020, 0.070, default=0.022, decimals=3, space="sell", optimize=True, load=True
    )
    # endregion
    slippage_protection = {"retries": 3, "max_slippage": -0.02}

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # self.gui_thread = None
        if not self.is_live_or_dry:
            from manigold_spaces import HyperOpt

            self.HyperOpt = HyperOpt
        logger.info(f"Buy strategies: {STRATEGIES}")

        if self.is_live_or_dry:
            self.trailing_stop = True
            self.use_custom_stoploss = False
        else:
            self.trailing_stop = False
            self.use_custom_stoploss = True

    @property
    def is_live_or_dry(self):
        return self.config["runmode"].value in ("live", "dry_run")

    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
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
        """
        Get strategy from strategy name
        :param strategy_name: strategy name
        :return: strategy class
        """
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
        """used in live"""
        t1 = time.time()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for pair in pairs:
                futures.append(executor.submit(self.analyze_pair, pair))
            for future in concurrent.futures.as_completed(futures):
                future.result()
        logger.info("Analyzed everything in %f seconds", time.time() - t1)
        # super().analyze(pairs)

    def advise_all_indicators(self, data: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        """only used in backtesting"""
        for s in STRATEGIES:
            self.get_strategy(s)
        logger.info("Loaded all strategies")

        # def worker(data_: DataFrame, metadata: dict):
        #     return {
        #         'pair': metadata['pair'],
        #         'data': self.advise_indicators(data_, metadata),
        #     }

        t1 = time.time()
        # new_data = {}
        # with ThreadPoolExecutor(max_workers=1) as executor:
        #     futures = []
        #     for pair, pair_data in data.items():
        #         futures.append(
        #             executor.submit(worker, pair_data.copy(), {'pair': pair})
        #         )
        #     for future in concurrent.futures.as_completed(futures):
        #         result = future.result()
        #         new_data[result['pair']] = result['data']
        indicators = super().advise_all_indicators(data)
        logger.info("Advise all elapsed: %s", time.time() - t1)
        return indicators

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        inf_frames: list[pd.DataFrame] = []

        for strategy_name in STRATEGIES:
            strategy = self.get_strategy(strategy_name)
            dataframe = strategy.advise_indicators(dataframe, metadata)
            # remove inf data from dataframe to avoid duplicates
            # _x or _y gets added to the inf columns that already exist
            inf_frames.append(dataframe.filter(regex=r"\w+_\d{1,2}[mhd]"))
            dataframe = dataframe[
                dataframe.columns.drop(
                    list(dataframe.filter(regex=r"\w+_\d{1,2}[mhd]"))
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
        dataframe.loc[:, "buy_tag"] = ""
        for strategy_name in strategies:
            # load instance of strategy_name
            strategy = self.get_strategy(strategy_name)
            # essentially call populate_buy_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            strategy_dataframe = strategy.advise_buy(dataframe.copy(), metadata)
            # create column for `strategy`
            strategy_dataframe.loc[:, "new_buy_tag"] = ""
            # On every candle that a buy signal is found, strategy_name
            # name will be added to its 'new_buy_tag' column
            strategy_dataframe.loc[
                strategy_dataframe.buy == 1, "new_buy_tag"
            ] = strategy_name
            # get the strategies that already exist for the row in the original dataframe
            strategy_dataframe.loc[:, "existing_buy_tag"] = dataframe["buy_tag"]
            # join the strategies found in the original dataframe's row with the new strategy
            strategy_dataframe.loc[:, "buy_tag"] = strategy_dataframe.apply(
                lambda x: ",".join((x["new_buy_tag"], x["existing_buy_tag"])).strip(
                    ","
                ),
                axis=1,
            )
            # update the original dataframe with the new strategies buy signals
            dataframe.loc[:, "buy_tag"] = strategy_dataframe["buy_tag"]
        # set `buy` column of rows with a buy_tag to 1
        dataframe.loc[dataframe.buy_tag != "", "buy"] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populates the sell signal for all strategies. This however will not set the sell signal.
        This will only add the strategy name to the `ensemble_sells` column.
        custom_sell will then sell based on the strategies in that column.
        """
        # dataframe.loc[:, 'ensemble_sells'] = ''
        dataframe.loc[:, "sell_tag"] = ""

        strategies = STRATEGIES.copy()
        # only populate strategies with open trades
        if self.is_live_or_dry:
            strategies_in_trades = set()
            trades: list[Trade] = Trade.get_open_trades()
            for t in trades:
                strategies_in_trades.update(t.buy_tag.split(","))
            strategies = strategies_in_trades
        for strategy_name in strategies:
            # If you know a better way of doing this, feel free to criticize this and let me know!
            # load instance of strategy_name
            strategy = self.get_strategy(strategy_name)

            # essentially call populate_sell_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            dataframe_copy = strategy.advise_sell(dataframe.copy(), metadata)

            # create column for `strategy`
            dataframe_copy.loc[:, "strategy"] = ""
            # On every candle that a buy signal is found, strategy_name
            # name will be added to its 'strategy' column
            dataframe_copy.loc[dataframe_copy.sell == 1, "strategy"] = strategy_name
            # get the strategies that already exist for the row in the original dataframe
            dataframe_copy.loc[:, "existing_sells"] = dataframe["sell_tag"]
            # join the strategies found in the original dataframe's row with the new strategy
            dataframe_copy.loc[:, "new_sell_tag"] = dataframe_copy.apply(
                lambda x: ",".join((x["strategy"], x["existing_sells"])).strip(","),
                axis=1,
            )
            # update the original dataframe with the new strategies sell signals
            dataframe.loc[:, "sell_tag"] = dataframe_copy["new_sell_tag"]
        # clear sell signals so they can be handled by custom_sell
        dataframe.loc[:, "sell"] = 0

        dataframe.drop(
            ["strategy"],
            axis=1,
            inplace=True,
            errors="ignore",
        )
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
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        # Obtain last available candle. Do not use current_time to look up latest candle, because
        # current_time points to current incomplete candle whose data is not available.
        # last_candle = dataframe.iloc[-1].squeeze()
        # In dry/live runs trade open date will not match candle open date therefore it must be
        # rounded.
        last_candle = dataframe.iloc[-1].squeeze()
        if not last_candle['sell_tag']:
            return
        # check to see if any candle has a sell signal
        for strategy_name in STRATEGIES:
            if strategy_name not in trade.buy_tag:
                continue
            # strategy = self.get_strategy(strategy_name)
            # regular sell signal. this does not cover custom_sells
            if (
                strategy_name in last_candle["sell_tag"]
                and strategy_name in trade.buy_tag
            ):
                return "sell_signal"
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
            should_sell.sell_reason = trade.buy_tag + "-" + should_sell.sell_reason
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
        for strategy_name in trade.buy_tag.split(","):
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
                    "Exception from %s in confirm_trade_exit", strategy_name, exc_info=e
                )
                continue
            if not trade_exit:
                return False

        # slippage protection from NotAnotherSMAOffsetStrategy
        try:
            state = self.slippage_protection["__pair_retries"]
        except KeyError:
            state = self.slippage_protection["__pair_retries"] = {}

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        candle = dataframe.iloc[-1].squeeze()

        slippage = (rate / candle["close"]) - 1
        if slippage < self.slippage_protection["max_slippage"]:
            pair_retries = state.get(pair, 0)
            if pair_retries < self.slippage_protection["retries"]:
                state[pair] = pair_retries + 1
                return False

        state[pair] = 0
        return True


# def custom_stop_loss_reached(
#     self,
#     current_rate: float,
#     trade: Trade,
#     current_time: datetime,
#     current_profit: float,
#     force_stoploss: float,
#     low: float = None,
#     high: float = None,
# ) -> SellCheckTuple:
#     """
#     Based on current profit of the trade and configured (trailing) stoploss,
#     decides to sell or not
#     :param current_profit: current profit as ratio
#     :param low: Low value of this candle, only set in backtesting
#     :param high: High value of this candle, only set in backtesting
#     """
#     stop_loss_value = force_stoploss if force_stoploss else self.stoploss
#
#     # Initiate stoploss with open_rate. Does nothing if stoploss is already set.
#     trade.adjust_stop_loss(trade.open_rate, stop_loss_value, initial=True)
#
#     if self.use_custom_stoploss and trade.stop_loss < (low or current_rate):
#         stop_loss_value = strategy_safe_wrapper(
#             self.custom_stoploss, default_retval=None
#         )(
#             pair=trade.pair,
#             trade=trade,
#             current_time=current_time,
#             current_rate=current_rate,
#             current_profit=current_profit,
#         )
#         # Sanity check - error cases will return None
#         if stop_loss_value:
#             # logger.info(f"{trade.pair} {stop_loss_value=} {current_profit=}")
#             trade.adjust_stop_loss(current_rate, stop_loss_value)
#         else:
#             logger.warning("CustomStoploss function did not return valid stoploss")
#
#     if self.trailing_stop and trade.stop_loss < (low or current_rate):
#         # trailing stoploss handling
#         sl_offset = self.trailing_stop_positive_offset
#
#         # Make sure current_profit is calculated using high for backtesting.
#         high_profit = current_profit if not high else trade.calc_profit_ratio(high)
#
#         # Don't update stoploss if trailing_only_offset_is_reached is true.
#         if not (self.trailing_only_offset_is_reached and high_profit < sl_offset):
#             # Specific handling for trailing_stop_positive
#             if self.trailing_stop_positive is not None and high_profit > sl_offset:
#                 stop_loss_value = self.trailing_stop_positive
#                 logger.debug(
#                     f"{trade.pair} - Using positive stoploss: {stop_loss_value} "
#                     f"offset: {sl_offset:.4g} profit: {current_profit:.4f}%"
#                 )
#
#             trade.adjust_stop_loss(high or current_rate, stop_loss_value)
#
#     # evaluate if the stoploss was hit if stoploss is not on exchange
#     # in Dry-Run, this handles stoploss logic as well, as the logic will not be different to
#     # regular stoploss handling.
#     if (trade.stop_loss >= (low or current_rate)) and (
#         not self.order_types.get('stoploss_on_exchange') or self.config['dry_run']
#     ):
#
#         sell_type = SellType.STOP_LOSS
#
#         # If initial stoploss is not the same as current one then it is trailing.
#         if trade.initial_stop_loss != trade.stop_loss:
#             sell_type = SellType.TRAILING_STOP_LOSS
#             logger.debug(
#                 f"{trade.pair} - HIT STOP: current price at {(low or current_rate):.6f}, "
#                 f"stoploss is {trade.stop_loss:.6f}, "
#                 f"initial stoploss was at {trade.initial_stop_loss:.6f}, "
#                 f"trade opened at {trade.open_rate:.6f}"
#             )
#             logger.debug(
#                 f"{trade.pair} - Trailing stop saved "
#                 f"{trade.stop_loss - trade.initial_stop_loss:.6f}"
#             )
#
#         return SellCheckTuple(sell_type=sell_type)
#
#     return SellCheckTuple(sell_type=SellType.NONE)
