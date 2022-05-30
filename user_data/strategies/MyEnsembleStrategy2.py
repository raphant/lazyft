import concurrent
import logging
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd
import rapidjson
from freqtrade.exchange import timeframe_to_prev_date
from freqtrade.misc import round_dict
from freqtrade.optimize.space import SKDecimal
from freqtrade.persistence import Trade
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import (
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
    stoploss_from_open,
)
from freqtrade.strategy.interface import ExitCheckTuple
from pandas import DataFrame
from scipy.interpolate import interp1d
from skopt.space import Categorical, Dimension, Integer

# warnings.filterwarnings(
#     'ignore',
#     'CustomStoploss.*',
# )
# warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)

sys.path.append(str(Path(__file__).parent))

logger = logging.getLogger(__name__)

ensemble_path = Path("user_data/strategies/ensemble.json")

STRATEGIES = []
if ensemble_path.exists():
    STRATEGIES = rapidjson.loads(ensemble_path.resolve().read_text())

keys_to_delete = [
    "minimal_roi",
    "stoploss",
    "ignore_roi_if_buy_signal",
]


class MyEnsembleStrategy2(IStrategy):
    loaded_strategies = {}

    stoploss = -0.31
    minimal_roi = {"0": 0.1669, "19": 0.049, "61": 0.023, "152": 0}

    # sell_profit_offset = (
    #     0.001  # it doesn't meant anything, just to guarantee there is a minimal profit.
    # )
    exit_sell_signal = True
    ignore_roi_if_buy_signal = True
    sell_profit_only = False

    # Trailing stoploss
    trailing_stop = False
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.016
    trailing_only_offset_is_reached = False

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
        "main_plot": {
            "buy_sell": {
                "sell_tag": {"color": "red"},
                "buy_tag": {"color": "blue"},
            },
        }
    }

    combo_sell_signal = IntParameter(1, len(STRATEGIES) + 1, default=2, space="buy")
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
        logger.info(f"Buy strategies: {STRATEGIES}")

        if self.is_live_or_dry:
            self.trailing_stop = True
            self.use_custom_stoploss = False
        else:
            self.trailing_stop = False
            self.use_custom_stoploss = True

    # def bot_loop_start(self, **kwargs) -> None:
    #     if not self.gui_thread:
    #         self.gui_thread = DataView.start_in_new_thread(self)

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
        # logger.info('Populating indicators for %s', metadata['pair'])
        t1 = time.time()
        indicators: list[DataFrame] = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for strategy_name in STRATEGIES:
                strategy = self.get_strategy(strategy_name)
                futures.append(
                    executor.submit(
                        strategy.advise_indicators, dataframe.copy(), metadata
                    )
                )
            for future in concurrent.futures.as_completed(futures):
                temp = future.result()
                # temp.set_index('date', inplace=True)
                indicators.append(
                    temp.drop(["open", "high", "low", "close", "volume"], axis=1)
                )
        # for strategy_name in STRATEGIES:
        #     # logger.info('Populating %s', strategy_name)
        #     strategy = self.get_strategy(strategy_name)
        #     # ohlcv + strategy indicators from populate_indicators
        #     t1 = time.time()
        #     temp = strategy.advise_indicators(dataframe.copy(), metadata)
        #     logger.info(
        #         'Advise indicators for %s took %.2f seconds',
        #         strategy_name,
        #         time.time() - t1,
        #     )
        #     indicators.append(
        #         temp.drop(['open', 'high', 'low', 'close', 'volume', 'date'], axis=1)
        #     )
        # remove inf data from dataframe to avoid duplicates
        # _x or _y gets added to the inf columns that already exist
        # inf_frames.append(dataframe.filter(regex=r'\w+_\d{1,2}[mhd]'))
        # dataframe = dataframe[
        #     dataframe.columns.drop(
        #         list(dataframe.filter(regex=r'\w+_\d{1,2}[mhd]'))
        #     )
        # ]

        # add informative data back to dataframe
        # for frame in inf_frames:
        #     for col, series in frame.iteritems():
        #         if col in dataframe:
        #             continue
        #         dataframe[col] = series
        for df in indicators:
            cols_to_use = df.columns.difference(dataframe.columns).to_list()
            cols_to_use.append("date")
            # dataframe = pd.concat([dataframe, df], axis=1)
            dataframe = pd.merge(dataframe, df[cols_to_use], on="date")
        # logger.info('Populating %s took %s seconds', metadata['pair'], time.time() - t1)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        strategies = STRATEGIES.copy()
        dataframe.loc[:, "ensemble_buy"] = ""
        dataframe.loc[:, "buy_tag"] = ""
        dataframe.loc[:, "buy"] = 0
        for strategy_name in strategies:
            strategy = self.get_strategy(strategy_name)
            strategy_indicators = strategy.advise_buy(dataframe.copy(), metadata)
            strategy_indicators.loc[:, "strategy"] = ""
            strategy_indicators.loc[
                strategy_indicators.buy == 1, "strategy"
            ] = strategy_name

            strategy_indicators.loc[:, "existing_buy"] = dataframe["ensemble_buy"]
            strategy_indicators.loc[:, "ensemble_buy"] = strategy_indicators.apply(
                lambda x: ",".join((x["strategy"], x["existing_buy"])).strip(","),
                axis=1,
            )
            dataframe.loc[:, "ensemble_buy"] = strategy_indicators["ensemble_buy"]

        dataframe.loc[dataframe.ensemble_buy != "", "buy"] = 1
        dataframe.loc[dataframe.buy == 1, "buy_tag"] = dataframe["ensemble_buy"]

        dataframe.drop(
            ["ensemble_buy", "existing_buy", "strategy", "buy_copy"],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        return dataframe

    @property
    def is_live_or_dry(self):
        return self.config["runmode"].value in ("live", "dry_run")

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # logger.info('Populating sell_trend for %s', metadata['pair'])
        dataframe.loc[:, "ensemble_sell"] = ""
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
            self.get_sell_trend_of_strategy(dataframe, metadata, strategy_name)

        dataframe.loc[dataframe.ensemble_sell != "", "sell"] = 1
        dataframe.loc[dataframe.sell == 1, "sell_tag"] = dataframe["ensemble_sell"]
        dataframe.loc[:, "sell"] = 0
        dataframe.drop(
            ["ensemble_sell", "existing_sell", "strategy"],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        return dataframe

    def get_sell_trend_of_strategy(self, dataframe, metadata, strategy_name):
        strategy = self.get_strategy(strategy_name)
        strategy_indicators = strategy.advise_sell(dataframe.copy(), metadata)
        strategy_indicators.loc[:, "strategy"] = ""
        strategy_indicators.loc[
            strategy_indicators.sell == 1, "strategy"
        ] = strategy_name
        strategy_indicators.loc[:, "existing_sell"] = dataframe["ensemble_sell"]
        strategy_indicators.loc[:, "ensemble_sell"] = strategy_indicators.apply(
            lambda x: ",".join((x["strategy"], x["existing_sell"])).strip(","), axis=1
        )
        dataframe.loc[:, "ensemble_sell"] = strategy_indicators["ensemble_sell"]

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
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        # Look up trade candle.
        trade_candle = dataframe.loc[dataframe["date"] == trade_date]
        if trade_candle.empty:
            return

        trade_candle = trade_candle.squeeze()
        # check to see if N number of strategies have a sell signal at this candle
        # strategy_sell_signals: list[str] = trade_candle['sell_tag'].split(',')
        for strategy_name in STRATEGIES:
            if strategy_name not in trade.buy_tag:
                continue
            # strategy = self.get_strategy(strategy_name)
            # regular sell signal. this does not cover custom_sells
            if (
                strategy_name in trade_candle["sell_tag"]
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
    ) -> ExitCheckTuple:
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
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
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

        candle = dataframe.iloc[-1].squeeze()

        slippage = (rate / candle["close"]) - 1
        if slippage < self.slippage_protection["max_slippage"]:
            pair_retries = state.get(pair, 0)
            if pair_retries < self.slippage_protection["retries"]:
                state[pair] = pair_retries + 1
                return False

        state[pair] = 0
        return True

    class HyperOpt:
        @staticmethod
        def generate_roi_table(params: Dict) -> Dict[int, float]:
            """
            Generates a Custom Long Continuous ROI Table with less gaps in it.
            Configurable step_size is loaded in from the Master MGM Framework.
            :param params: (Dict) Base Parameters used for the ROI Table calculation
            :return Dict: Generated ROI Table
            """
            step = MyEnsembleStrategy.roi_table_step_size

            minimal_roi = {
                0: params["roi_p1"] + params["roi_p2"] + params["roi_p3"],
                params["roi_t3"]: params["roi_p1"] + params["roi_p2"],
                params["roi_t3"] + params["roi_t2"]: params["roi_p1"],
                params["roi_t3"] + params["roi_t2"] + params["roi_t1"]: 0,
            }

            max_value = max(map(int, minimal_roi.keys()))
            f = interp1d(list(map(int, minimal_roi.keys())), list(minimal_roi.values()))
            x = list(range(0, max_value, step))
            y = list(map(float, map(f, x)))
            if y[-1] != 0:
                x.append(x[-1] + step)
                y.append(0)
            return dict(zip(x, y))

        @staticmethod
        def roi_space() -> list[Dimension]:
            """
            Create a ROI space. Defines values to search for each ROI steps.
            This method implements adaptive roi HyperSpace with varied ranges for parameters which automatically adapts
            to the un-zoomed informative_timeframe used by the MGM Framework during BackTesting & HyperOpting.
            :return List: Generated ROI Space
            """

            # Default scaling coefficients for the ROI HyperSpace. Can be changed to adjust resulting ranges of the ROI
            # tables. Increase if you need wider ranges in the ROI HyperSpace, decrease if shorter ranges are needed:
            # roi_t_alpha: Limits for the time intervals in the ROI Tables. Components are scaled linearly.
            roi_t_alpha = MyEnsembleStrategy.roi_time_interval_scaling
            # roi_p_alpha: Limits for the ROI value steps. Components are scaled logarithmically.
            roi_p_alpha = MyEnsembleStrategy.roi_value_step_scaling

            # Load in the un-zoomed timeframe size from the Master MGM Framework
            timeframe_min = 5

            # The scaling is designed so that it maps exactly to the legacy Freqtrade roi_space()
            # method for the 5m timeframe.
            roi_t_scale = timeframe_min
            roi_p_scale = math.log1p(timeframe_min) / math.log1p(5)
            roi_limits = {
                "roi_t1_min": int(10 * roi_t_scale * roi_t_alpha),
                "roi_t1_max": int(120 * roi_t_scale * roi_t_alpha),
                "roi_t2_min": int(10 * roi_t_scale * roi_t_alpha),
                "roi_t2_max": int(60 * roi_t_scale * roi_t_alpha),
                "roi_t3_min": int(10 * roi_t_scale * roi_t_alpha),
                "roi_t3_max": int(40 * roi_t_scale * roi_t_alpha),
                "roi_p1_min": 0.01 * roi_p_scale * roi_p_alpha,
                "roi_p1_max": 0.04 * roi_p_scale * roi_p_alpha,
                "roi_p2_min": 0.01 * roi_p_scale * roi_p_alpha,
                "roi_p2_max": 0.07 * roi_p_scale * roi_p_alpha,
                "roi_p3_min": 0.01 * roi_p_scale * roi_p_alpha,
                "roi_p3_max": 0.20 * roi_p_scale * roi_p_alpha,
            }

            # Generate MGM's custom long continuous ROI table
            logger.debug(f"Using ROI space limits: {roi_limits}")
            p = {
                "roi_t1": roi_limits["roi_t1_min"],
                "roi_t2": roi_limits["roi_t2_min"],
                "roi_t3": roi_limits["roi_t3_min"],
                "roi_p1": roi_limits["roi_p1_min"],
                "roi_p2": roi_limits["roi_p2_min"],
                "roi_p3": roi_limits["roi_p3_min"],
            }
            logger.info(
                f"Min ROI table: {round_dict(MyEnsembleStrategy.HyperOpt.generate_roi_table(p), 3)}"
            )
            p = {
                "roi_t1": roi_limits["roi_t1_max"],
                "roi_t2": roi_limits["roi_t2_max"],
                "roi_t3": roi_limits["roi_t3_max"],
                "roi_p1": roi_limits["roi_p1_max"],
                "roi_p2": roi_limits["roi_p2_max"],
                "roi_p3": roi_limits["roi_p3_max"],
            }
            logger.info(
                f"Max ROI table: {round_dict(MyEnsembleStrategy.HyperOpt.generate_roi_table(p), 3)}"
            )

            return [
                Integer(
                    roi_limits["roi_t1_min"], roi_limits["roi_t1_max"], name="roi_t1"
                ),
                Integer(
                    roi_limits["roi_t2_min"], roi_limits["roi_t2_max"], name="roi_t2"
                ),
                Integer(
                    roi_limits["roi_t3_min"], roi_limits["roi_t3_max"], name="roi_t3"
                ),
                SKDecimal(
                    roi_limits["roi_p1_min"],
                    roi_limits["roi_p1_max"],
                    decimals=3,
                    name="roi_p1",
                ),
                SKDecimal(
                    roi_limits["roi_p2_min"],
                    roi_limits["roi_p2_max"],
                    decimals=3,
                    name="roi_p2",
                ),
                SKDecimal(
                    roi_limits["roi_p3_min"],
                    roi_limits["roi_p3_max"],
                    decimals=3,
                    name="roi_p3",
                ),
            ]

        @staticmethod
        def stoploss_space() -> list[Dimension]:
            """
            Define custom stoploss search space with configurable parameters for the Stoploss Value to search.
            Override it if you need some different range for the parameter in the 'stoploss' optimization hyperspace.
            :return List: Generated Stoploss Space
            """
            # noinspection PyTypeChecker
            return [
                SKDecimal(
                    MyEnsembleStrategy.stoploss_max_value,
                    MyEnsembleStrategy.stoploss_min_value,
                    decimals=3,
                    name="stoploss",
                )
            ]

        # noinspection PyTypeChecker
        @staticmethod
        def trailing_space() -> list[Dimension]:
            """
            Define custom trailing search space with parameters configurable in 'mgm-config'
            :return List: Generated Trailing Space
            """
            return [
                # It was decided to always set trailing_stop is to True if the 'trailing' hyperspace
                # is used. Otherwise hyperopt will vary other parameters that won't have effect if
                # trailing_stop is set False.
                # This parameter is included into the hyperspace dimensions rather than assigning
                # it explicitly in the code in order to have it printed in the results along with
                # other 'trailing' hyperspace parameters.
                Categorical([True], name="trailing_stop"),
                SKDecimal(
                    MyEnsembleStrategy.trailing_stop_positive_min_value,
                    MyEnsembleStrategy.trailing_stop_positive_max_value,
                    decimals=3,
                    name="trailing_stop_positive",
                ),
                # 'trailing_stop_positive_offset' should be greater than 'trailing_stop_positive',
                # so this intermediate parameter is used as the value of the difference between
                # them. The value of the 'trailing_stop_positive_offset' is constructed in the
                # generate_trailing_params() method.
                # This is similar to the hyperspace dimensions used for constructing the ROI tables.
                SKDecimal(
                    MyEnsembleStrategy.trailing_stop_positive_offset_min_value,
                    MyEnsembleStrategy.trailing_stop_positive_offset_max_value,
                    decimals=3,
                    name="trailing_stop_positive_offset_p1",
                ),
                Categorical([True, False], name="trailing_only_offset_is_reached"),
            ]


# def custom_stop_loss_reached(
#     self,
#     current_rate: float,
#     trade: Trade,
#     current_time: datetime,
#     current_profit: float,
#     force_stoploss: float,
#     low: float = None,
#     high: float = None,
# ) -> ExitCheckTuple:
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
#         return ExitCheckTuple(sell_type=sell_type)
#
#     return ExitCheckTuple(sell_type=SellType.NONE)
