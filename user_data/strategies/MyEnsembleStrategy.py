import concurrent
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd
import rapidjson
from freqtrade.enums import SellType
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
if ensemble_path.exists():
    STRATEGIES = rapidjson.loads(ensemble_path.resolve().read_text())

keys_to_delete = [
    "minimal_roi",
    "stoploss",
    "ignore_roi_if_buy_signal",
]


class MyEnsembleStrategy(IStrategy):
    """Inspiration from"""

    loaded_strategies = {}

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

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

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
        for pair in pairs:
            try:
                self.analyze_pair(pair)
            except Exception as e:
                logger.exception('Error analyzing pair %s', pair, exc_info=e)

    def advise_all_indicators(self, data: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        """only used in backtesting"""
        for s in STRATEGIES:
            self.get_strategy(s)
        logger.info("Loaded all strategies")
        t1 = time.time()
        indicators = super().advise_all_indicators(data)
        logger.info("Advise all elapsed: %s", time.time() - t1)
        return indicators

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        inf_frames: list[pd.DataFrame] = []
        frames = []
        for strategy_name in STRATEGIES:
            strategy = self.get_strategy(strategy_name)
            df = strategy.advise_indicators(dataframe, metadata)
            # remove inf data from dataframe to avoid duplicates
            # _x or _y gets added to the inf columns that already exist
            inf_frames.append(df.filter(regex=r"\w+_\d{1,2}[mhd]"))
            df = df[df.columns.drop(list(df.filter(regex=r"\w+_\d{1,2}[mhd]")))]
            frames.append(df)
        # join all frames
        dataframe = pd.concat(frames, axis=1)
        dataframe = dataframe.loc[:, ~dataframe.columns.duplicated()]
        # add informative data back to dataframe
        for frame in inf_frames:
            for col, series in frame.iteritems():
                if col in dataframe:
                    continue
                dataframe.loc[:, col] = series
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populates the buy signal for all strategies. Each strategy with a buy signal will be
        added to the buy_tag. Open to constructive criticism!
        """
        dataframe.loc[:, 'buy_tag'] = ''

        strategies = STRATEGIES.copy()
        for strategy_name in strategies:
            # load instance of strategy_name
            strategy = self.get_strategy(strategy_name)
            # essentially call populate_buy_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            strategy_dataframe = strategy.advise_buy(dataframe.copy(), metadata)
            dataframe.loc[strategy_dataframe.buy == 1, 'buy_tag'] += f'{strategy_name} '
            for k in strategy_dataframe:
                if k not in dataframe:
                    dataframe[k] = strategy_dataframe[k]
        dataframe.loc[dataframe.buy_tag != '', 'buy'] = 1
        dataframe['buy_tag'] = dataframe['buy_tag'].str.strip()
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populates the sell signal for all strategies. This however will not set the sell signal.
        This will only add the strategy name to the `ensemble_sells` column.
        custom_sell will then sell based on the strategies in that column.
        """
        dataframe.loc[:, 'exit_tag'] = ''

        # only populate strategies with open trades
        strategies = self.strategies_with_open_trades()
        for strategy_name in strategies:
            # If you know a better way of doing this, feel free to criticize this and let me know!
            # load instance of strategy_name
            strategy = self.get_strategy(strategy_name)

            # essentially call populate_sell_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            dataframe_copy = strategy.advise_sell(dataframe.copy(), metadata)

            dataframe.loc[dataframe_copy.sell == 1, 'exit_tag'] += f'{strategy_name} '
            for k in dataframe_copy:
                if k not in dataframe:
                    dataframe[k] = dataframe_copy[k]
        dataframe.loc[dataframe.exit_tag != '', 'sell'] = 1
        dataframe['exit_tag'] = dataframe['exit_tag'].str.strip()
        return dataframe

    def strategies_with_open_trades(self):
        strategies = STRATEGIES.copy()
        if any(Trade.get_open_trades()) and self.is_live_or_dry:
            strategies_in_trades = set()
            trades: list[Trade] = Trade.get_open_trades()
            for t in trades:
                strategies_in_trades.update(t.buy_tag.split())
            strategies = strategies_in_trades
        return strategies

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
        # go through each strategy and ask if it should sell
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # do not honor the sell signal of a strategy that is not in the buy tag
        if sell:
            buy_strategies = set(trade.buy_tag.split())
            sell_strategies = set(last_candle['exit_tag'].split())
            # make sure at least 1 sell strategy is in the buy strategies
            if not sell_strategies.intersection(buy_strategies):
                sell = False
            else:
                return SellCheckTuple(
                    SellType.SELL_SIGNAL,
                    f'({last_candle["exit_tag"]}-ss',
                )

        for strategy_name in trade.buy_tag.split():
            strategy = self.get_strategy(strategy_name)
            sell_check = strategy.should_sell(
                trade, rate, date, buy, sell, low, high, force_stoploss
            )
            if sell_check is not None:
                sell_check.sell_reason = f'{strategy_name}-{sell_check.sell_reason}'
                return sell_check
        return super().should_sell(
            trade, rate, date, buy, sell, low, high, force_stoploss
        )

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
        for strategy_name in trade.buy_tag.split():
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
