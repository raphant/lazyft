import json
import pathlib
import sys
from datetime import datetime
from functools import reduce
from pathlib import Path

import numpy as np

# Get rid of pandas warnings during backtesting
import pandas as pd
import rapidjson
import talib.abstract as ta
from pandas import DataFrame, Series

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    merge_informative_pair,
    IntParameter,
    DecimalParameter,
    CategoricalParameter,
)

pd.options.mode.chained_assignment = None  # default='warn'

# Strategy specific imports, files must reside in same folder as strategy

sys.path.append(str(Path(__file__).parent))


"""
Solipsis - By @werkkrew

Credits - 
@JimmyNixx for many of the ideas used throughout as well as helping me stay motivated throughout development!
@rk for submitting many PR's that have made this strategy possible! 

I ask for nothing in return except that if you make changes which bring you greater success than what has been provided, you share those ideas back to 
the community. Also, please don't nag me with a million questions and especially don't blame me if you lose a ton of money using this.

I take no responsibility for any success or failure you have using this strategy.

VERSION: 5.2.1
"""

# region custom indicators
"""
Solipsis Custom Indicators and Maths
"""


"""
Misc. Helper Functions
"""


def same_length(bigger, shorter):
    return np.concatenate(
        (np.full((bigger.shape[0] - shorter.shape[0]), np.nan), shorter)
    )


"""
Maths
"""


def linear_growth(
    start: float, end: float, start_time: int, end_time: int, trade_time: int
) -> float:
    """
    Simple linear growth function. Grows from start to end after end_time minutes (starts after start_time minutes)
    """
    time = max(0, trade_time - start_time)
    rate = (end - start) / (end_time - start_time)

    return min(end, start + (rate * time))


def linear_decay(
    start: float, end: float, start_time: int, end_time: int, trade_time: int
) -> float:
    """
    Simple linear decay function. Decays from start to end after end_time minutes (starts after start_time minutes)
    """
    time = max(0, trade_time - start_time)
    rate = (start - end) / (end_time - start_time)

    return max(end, start - (rate * time))


"""
TA Indicators
"""


def zema(dataframe, period, field='close'):
    """
    Source: https://github.com/freqtrade/technical/blob/master/technical/indicators/overlap_studies.py#L79
    Modified slightly to use ta.EMA instead of technical ema
    """
    df = dataframe.copy()

    df['ema1'] = ta.EMA(df[field], timeperiod=period)
    df['ema2'] = ta.EMA(df['ema1'], timeperiod=period)
    df['d'] = df['ema1'] - df['ema2']
    df['zema'] = df['ema1'] + df['d']

    return df['zema']


def RMI(dataframe, *, length=20, mom=5):
    """
    Source: https://github.com/freqtrade/technical/blob/master/technical/indicators/indicators.py#L912
    """
    df = dataframe.copy()

    df['maxup'] = (df['close'] - df['close'].shift(mom)).clip(lower=0)
    df['maxdown'] = (df['close'].shift(mom) - df['close']).clip(lower=0)

    df.fillna(0, inplace=True)

    df["emaInc"] = ta.EMA(df, price='maxup', timeperiod=length)
    df["emaDec"] = ta.EMA(df, price='maxdown', timeperiod=length)

    df['RMI'] = np.where(
        df['emaDec'] == 0, 0, 100 - 100 / (1 + df["emaInc"] / df["emaDec"])
    )

    return df["RMI"]


def mastreak(dataframe: DataFrame, period: int = 4, field='close') -> Series:
    """
    MA Streak
    Port of: https://www.tradingview.com/script/Yq1z7cIv-MA-Streak-Can-Show-When-a-Run-Is-Getting-Long-in-the-Tooth/
    """
    df = dataframe.copy()

    avgval = zema(df, period, field)

    arr = np.diff(avgval)
    pos = np.clip(arr, 0, 1).astype(bool).cumsum()
    neg = np.clip(arr, -1, 0).astype(bool).cumsum()
    streak = np.where(
        arr >= 0,
        pos - np.maximum.accumulate(np.where(arr <= 0, pos, 0)),
        -neg + np.maximum.accumulate(np.where(arr >= 0, neg, 0)),
    )

    res = same_length(df['close'], streak)

    return res


def pcc(dataframe: DataFrame, period: int = 20, mult: int = 2):
    """
    Percent Change Channel
    PCC is like KC unless it uses percentage changes in price to set channel distance.
    https://www.tradingview.com/script/6wwAWXA1-MA-Streak-Change-Channel/
    """
    df = dataframe.copy()

    df['previous_close'] = df['close'].shift()

    df['close_change'] = (
        (df['close'] - df['previous_close']) / df['previous_close'] * 100
    )
    df['high_change'] = (df['high'] - df['close']) / df['close'] * 100
    df['low_change'] = (df['low'] - df['close']) / df['close'] * 100

    df['delta'] = df['high_change'] - df['low_change']

    mid = zema(df, period, 'close_change')
    rangema = zema(df, period, 'delta')

    upper = mid + rangema * mult
    lower = mid - rangema * mult

    return upper, rangema, lower


def SSLChannels(dataframe, length=10, mode='sma'):
    """
    Source: https://www.tradingview.com/script/xzIoaIJC-SSL-channel/
    Source: https://github.com/freqtrade/technical/blob/master/technical/indicators/indicators.py#L1025
    Usage:
        dataframe['sslDown'], dataframe['sslUp'] = SSLChannels(dataframe, 10)
    """
    if mode not in ('sma'):
        raise ValueError(f"Mode {mode} not supported yet")

    df = dataframe.copy()

    if mode == 'sma':
        df['smaHigh'] = df['high'].rolling(length).mean()
        df['smaLow'] = df['low'].rolling(length).mean()

    df['hlv'] = np.where(
        df['close'] > df['smaHigh'], 1, np.where(df['close'] < df['smaLow'], -1, np.NAN)
    )
    df['hlv'] = df['hlv'].ffill()

    df['sslDown'] = np.where(df['hlv'] < 0, df['smaHigh'], df['smaLow'])
    df['sslUp'] = np.where(df['hlv'] < 0, df['smaLow'], df['smaHigh'])

    return df['sslDown'], df['sslUp']


def SSLChannels_ATR(dataframe, length=7):
    """
    SSL Channels with ATR: https://www.tradingview.com/script/SKHqWzql-SSL-ATR-channel/
    Credit to @JimmyNixx for python
    """
    df = dataframe.copy()

    df['ATR'] = ta.ATR(df, timeperiod=14)
    df['smaHigh'] = df['high'].rolling(length).mean() + df['ATR']
    df['smaLow'] = df['low'].rolling(length).mean() - df['ATR']
    df['hlv'] = np.where(
        df['close'] > df['smaHigh'], 1, np.where(df['close'] < df['smaLow'], -1, np.NAN)
    )
    df['hlv'] = df['hlv'].ffill()
    df['sslDown'] = np.where(df['hlv'] < 0, df['smaHigh'], df['smaLow'])
    df['sslUp'] = np.where(df['hlv'] < 0, df['smaLow'], df['smaHigh'])

    return df['sslDown'], df['sslUp']


def WaveTrend(dataframe, chlen=10, avg=21, smalen=4):
    """
    WaveTrend Ocillator by LazyBear
    https://www.tradingview.com/script/2KE8wTuF-Indicator-WaveTrend-Oscillator-WT/
    """
    df = dataframe.copy()

    df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
    df['esa'] = ta.EMA(df['hlc3'], timeperiod=chlen)
    df['d'] = ta.EMA((df['hlc3'] - df['esa']).abs(), timeperiod=chlen)
    df['ci'] = (df['hlc3'] - df['esa']) / (0.015 * df['d'])
    df['tci'] = ta.EMA(df['ci'], timeperiod=avg)

    df['wt1'] = df['tci']
    df['wt2'] = ta.SMA(df['wt1'], timeperiod=smalen)
    df['wt1-wt2'] = df['wt1'] - df['wt2']

    return df['wt1'], df['wt2']


def T3(dataframe, length=5):
    """
    T3 Average by HPotter on Tradingview
    https://www.tradingview.com/script/qzoC9H1I-T3-Average/
    """
    df = dataframe.copy()

    df['xe1'] = ta.EMA(df['close'], timeperiod=length)
    df['xe2'] = ta.EMA(df['xe1'], timeperiod=length)
    df['xe3'] = ta.EMA(df['xe2'], timeperiod=length)
    df['xe4'] = ta.EMA(df['xe3'], timeperiod=length)
    df['xe5'] = ta.EMA(df['xe4'], timeperiod=length)
    df['xe6'] = ta.EMA(df['xe5'], timeperiod=length)
    b = 0.7
    c1 = -b * b * b
    c2 = 3 * b * b + 3 * b * b * b
    c3 = -6 * b * b - 3 * b - 3 * b * b * b
    c4 = 1 + 3 * b + b * b * b + 3 * b * b
    df['T3Average'] = c1 * df['xe6'] + c2 * df['xe5'] + c3 * df['xe4'] + c4 * df['xe3']

    return df['T3Average']


def SROC(dataframe, roclen=21, emalen=13, smooth=21):
    df = dataframe.copy()

    roc = ta.ROC(df, timeperiod=roclen)
    ema = ta.EMA(df, timeperiod=emalen)
    sroc = ta.ROC(ema, timeperiod=smooth)

    return sroc


# endregion
class Solipsis(IStrategy):
    ## Buy Space Hyperopt Variables

    # Base Pair Params
    buy_base_mp = IntParameter(
        10, 50, default=30, space='buy', load=True, optimize=True
    )
    buy_base_rmi_max = IntParameter(
        30, 60, default=50, space='buy', load=True, optimize=True
    )
    buy_base_rmi_min = IntParameter(
        0, 30, default=20, space='buy', load=True, optimize=True
    )
    buy_base_ma_streak = IntParameter(
        1, 4, default=1, space='buy', load=True, optimize=True
    )
    buy_base_rmi_streak = IntParameter(
        3, 8, default=3, space='buy', load=True, optimize=True
    )
    buy_base_trigger = CategoricalParameter(
        ['pcc', 'rmi', 'none'], default='rmi', space='buy', load=True, optimize=True
    )
    buy_inf_pct_adr = DecimalParameter(
        0.70, 0.99, default=0.80, space='buy', load=True, optimize=True
    )
    # BTC Informative
    buy_xbtc_guard = CategoricalParameter(
        ['strict', 'lazy', 'none'], default='lazy', space='buy', optimize=True
    )
    buy_xbtc_base_rmi = IntParameter(
        20, 70, default=40, space='buy', load=True, optimize=True
    )
    # BTC / ETH Stake Parameters
    buy_xtra_base_stake_rmi = IntParameter(
        10, 50, default=50, space='buy', load=True, optimize=True
    )
    buy_xtra_base_fiat_rmi = IntParameter(
        30, 70, default=50, space='buy', load=True, optimize=True
    )

    ## Sell Space Params are being used for both custom_stoploss and custom_sell

    # Custom Sell Profit (formerly Dynamic ROI)
    sell_roi_type = CategoricalParameter(
        ['static', 'decay', 'step'],
        default='step',
        space='sell',
        load=True,
        optimize=True,
    )
    sell_roi_time = IntParameter(
        720, 1440, default=720, space='sell', load=True, optimize=True
    )
    sell_roi_start = DecimalParameter(
        0.01, 0.05, default=0.01, space='sell', load=True, optimize=True
    )
    sell_roi_end = DecimalParameter(
        0.0, 0.01, default=0, space='sell', load=True, optimize=True
    )
    sell_trend_type = CategoricalParameter(
        ['rmi', 'ssl', 'candle', 'any', 'none'],
        default='any',
        space='sell',
        load=True,
        optimize=True,
    )
    sell_pullback = CategoricalParameter(
        [True, False], default=True, space='sell', load=True, optimize=True
    )
    sell_pullback_amount = DecimalParameter(
        0.005, 0.03, default=0.01, space='sell', load=True, optimize=True
    )
    sell_pullback_respect_roi = CategoricalParameter(
        [True, False], default=False, space='sell', load=True, optimize=True
    )
    sell_endtrend_respect_roi = CategoricalParameter(
        [True, False], default=False, space='sell', load=True, optimize=True
    )

    # Custom Stoploss
    sell_stop_loss_threshold = DecimalParameter(
        -0.05, -0.01, default=-0.03, space='sell', load=True, optimize=True
    )
    sell_stop_bail_how = CategoricalParameter(
        ['roc', 'time', 'any', 'none'],
        default='none',
        space='sell',
        load=True,
        optimize=True,
    )
    sell_stop_bail_roc = DecimalParameter(
        -5.0, -1.0, default=-3.0, space='sell', load=True, optimize=True
    )
    sell_stop_bail_time = IntParameter(
        60, 1440, default=720, space='sell', load=True, optimize=True
    )
    sell_stop_bail_time_trend = CategoricalParameter(
        [True, False], default=True, space='sell', load=True, optimize=True
    )

    timeframe = '5m'
    inf_timeframe = '1h'

    buy_params = {}

    sell_params = {}

    minimal_roi = {"0": 100}

    stoploss = -0.99
    use_custom_stoploss = True

    # Recommended
    use_sell_signal = True
    sell_profit_only = True
    ignore_roi_if_buy_signal = True

    # Required
    startup_candle_count: int = 233
    process_only_new_candles = False

    # Strategy Specific Variable Storage
    custom_trade_info = {}
    custom_fiat = "USD"  # Only relevant if stake is BTC or ETH
    custom_btc_inf = False  # Don't change this.

    from util import load

    if locals()['__module__'] == locals()['__qualname__']:
        locals().update(load(locals()['__qualname__']))

    """
    Informative Pair Definitions
    """

    def informative_pairs(self):
        # add all whitelisted pairs on informative timeframe
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.inf_timeframe) for pair in pairs]

        # add extra informative pairs if the stake is BTC or ETH
        if self.config['stake_currency'] in ('BTC', 'ETH'):
            for pair in pairs:
                coin, stake = pair.split('/')
                coin_fiat = f"{coin}/{self.custom_fiat}"
                informative_pairs += [(coin_fiat, self.timeframe)]

            stake_fiat = f"{self.config['stake_currency']}/{self.custom_fiat}"
            informative_pairs += [(stake_fiat, self.timeframe)]
        # if BTC/STAKE is not in whitelist, add it as an informative pair on both timeframes
        else:
            btc_stake = f"BTC/{self.config['stake_currency']}"
            if not btc_stake in pairs:
                informative_pairs += [(btc_stake, self.timeframe)]

        return informative_pairs

    """
    Indicator Definitions
    """

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if not metadata['pair'] in self.custom_trade_info:
            self.custom_trade_info[metadata['pair']] = {}
            if not 'had-trend' in self.custom_trade_info[metadata["pair"]]:
                self.custom_trade_info[metadata['pair']]['had-trend'] = False

        ## Base Timeframe / Pair

        # Kaufmann Adaptive Moving Average
        dataframe['kama'] = ta.KAMA(dataframe, length=233)

        # RMI: https://www.tradingview.com/script/kwIt9OgQ-Relative-Momentum-Index/
        dataframe['rmi'] = RMI(dataframe, length=24, mom=5)

        # Momentum Pinball: https://www.tradingview.com/script/fBpVB1ez-Momentum-Pinball-Indicator/
        dataframe['roc-mp'] = ta.ROC(dataframe, timeperiod=1)
        dataframe['mp'] = ta.RSI(dataframe['roc-mp'], timeperiod=3)

        # MA Streak: https://www.tradingview.com/script/Yq1z7cIv-MA-Streak-Can-Show-When-a-Run-Is-Getting-Long-in-the-Tooth/
        dataframe['mastreak'] = mastreak(dataframe, period=4)

        # Percent Change Channel: https://www.tradingview.com/script/6wwAWXA1-MA-Streak-Change-Channel/
        upper, mid, lower = pcc(dataframe, period=40, mult=3)
        dataframe['pcc-lowerband'] = lower
        dataframe['pcc-upperband'] = upper

        lookup_idxs = dataframe.index.values - (abs(dataframe['mastreak'].values) + 1)
        valid_lookups = lookup_idxs >= 0
        dataframe['sbc'] = np.nan
        dataframe.loc[valid_lookups, 'sbc'] = dataframe['close'].to_numpy()[
            lookup_idxs[valid_lookups].astype(int)
        ]

        dataframe['streak-roc'] = (
            100 * (dataframe['close'] - dataframe['sbc']) / dataframe['sbc']
        )

        # Trends, Peaks and Crosses
        dataframe['candle-up'] = np.where(dataframe['close'] >= dataframe['open'], 1, 0)
        dataframe['candle-up-trend'] = np.where(
            dataframe['candle-up'].rolling(5).sum() >= 3, 1, 0
        )

        dataframe['rmi-up'] = np.where(
            dataframe['rmi'] >= dataframe['rmi'].shift(), 1, 0
        )
        dataframe['rmi-up-trend'] = np.where(
            dataframe['rmi-up'].rolling(5).sum() >= 3, 1, 0
        )

        dataframe['rmi-dn'] = np.where(
            dataframe['rmi'] <= dataframe['rmi'].shift(), 1, 0
        )
        dataframe['rmi-dn-count'] = dataframe['rmi-dn'].rolling(8).sum()

        dataframe['streak-bo'] = np.where(
            dataframe['streak-roc'] < dataframe['pcc-lowerband'], 1, 0
        )
        dataframe['streak-bo-count'] = dataframe['streak-bo'].rolling(8).sum()

        # Indicators used only for ROI and Custom Stoploss
        ssldown, sslup = SSLChannels_ATR(dataframe, length=21)
        dataframe['sroc'] = SROC(dataframe, roclen=21, emalen=13, smooth=21)
        dataframe['ssl-dir'] = np.where(sslup > ssldown, 'up', 'down')

        # Base pair informative timeframe indicators
        informative = self.dp.get_pair_dataframe(
            pair=metadata['pair'], timeframe=self.inf_timeframe
        )

        # Get the "average day range" between the 1d high and 1d low to set up guards
        informative['1d-high'] = informative['close'].rolling(24).max()
        informative['1d-low'] = informative['close'].rolling(24).min()
        informative['adr'] = informative['1d-high'] - informative['1d-low']

        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, self.inf_timeframe, ffill=True
        )

        # Other stake specific informative indicators
        # e.g if stake is BTC and current coin is XLM (pair: XLM/BTC)
        if self.config['stake_currency'] in ('BTC', 'ETH'):
            coin, stake = metadata['pair'].split('/')
            fiat = self.custom_fiat
            coin_fiat = f"{coin}/{fiat}"
            stake_fiat = f"{stake}/{fiat}"

            # Informative COIN/FIAT e.g. XLM/USD - Base Timeframe
            coin_fiat_tf = self.dp.get_pair_dataframe(
                pair=coin_fiat, timeframe=self.timeframe
            )
            dataframe[f"{fiat}_rmi"] = RMI(coin_fiat_tf, length=55, mom=5)

            # Informative STAKE/FIAT e.g. BTC/USD - Base Timeframe
            stake_fiat_tf = self.dp.get_pair_dataframe(
                pair=stake_fiat, timeframe=self.timeframe
            )
            dataframe[f"{stake}_rmi"] = RMI(stake_fiat_tf, length=55, mom=5)

        # Informatives for BTC/STAKE if not in whitelist
        else:
            pairs = self.dp.current_whitelist()
            btc_stake = f"BTC/{self.config['stake_currency']}"
            if not btc_stake in pairs:
                self.custom_btc_inf = True
                # BTC/STAKE - Base Timeframe
                btc_stake_tf = self.dp.get_pair_dataframe(
                    pair=btc_stake, timeframe=self.timeframe
                )
                dataframe['BTC_rmi'] = RMI(btc_stake_tf, length=55, mom=5)
                dataframe['BTC_close'] = btc_stake_tf['close']
                dataframe['BTC_kama'] = ta.KAMA(btc_stake_tf, length=144)

        return dataframe

    """
    Buy Signal
    """

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # Informative Timeframe Guards
        conditions.append(
            (
                dataframe['close']
                <= dataframe[f"1d-low_{self.inf_timeframe}"]
                + (self.buy_inf_pct_adr.value * dataframe[f"adr_{self.inf_timeframe}"])
            )
        )

        # Base Timeframe Guards
        conditions.append(
            (dataframe['rmi-dn-count'] >= self.buy_base_rmi_streak.value)
            & (dataframe['streak-bo-count'] >= self.buy_base_ma_streak.value)
            & (dataframe['rmi'] <= self.buy_base_rmi_max.value)
            & (dataframe['rmi'] >= self.buy_base_rmi_min.value)
            & (dataframe['mp'] <= self.buy_base_mp.value)
        )

        # Base Timeframe Trigger
        if self.buy_base_trigger.value == 'pcc':
            conditions.append(
                qtpylib.crossed_above(
                    dataframe['streak-roc'], dataframe['pcc-lowerband']
                )
            )

        if self.buy_base_trigger.value == 'rmi':
            conditions.append(dataframe['rmi-up-trend'] == 1)

        # Extra conditions for */BTC and */ETH stakes on additional informative pairs
        if self.config['stake_currency'] in ('BTC', 'ETH'):
            conditions.append(
                (
                    dataframe[f"{self.custom_fiat}_rmi"]
                    > self.buy_xtra_base_fiat_rmi.value
                )
                | (
                    dataframe[f"{self.config['stake_currency']}_rmi"]
                    < self.buy_xtra_base_stake_rmi.value
                )
            )
        # Extra conditions for BTC/STAKE if not in whitelist
        else:
            if self.custom_btc_inf:
                if self.buy_xbtc_guard.value == 'strict':
                    conditions.append(
                        (
                            (dataframe['BTC_rmi'] > self.buy_xbtc_base_rmi.value)
                            & (dataframe['BTC_close'] > dataframe['BTC_kama'])
                        )
                    )
                if self.buy_xbtc_guard.value == 'lazy':
                    conditions.append(
                        (dataframe['close'] > dataframe['kama'])
                        | (
                            (dataframe['BTC_rmi'] > self.buy_xbtc_base_rmi.value)
                            & (dataframe['BTC_close'] > dataframe['BTC_kama'])
                        )
                    )

        conditions.append(dataframe['volume'].gt(0))

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1

        return dataframe

    """
    Sell Signal
    """

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sell'] = 0

        return dataframe

    """
    Custom Stoploss
    """

    def custom_stoploss(
        self,
        pair: str,
        trade: 'Trade',
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(
            pair=pair, timeframe=self.timeframe
        )
        last_candle = dataframe.iloc[-1].squeeze()
        trade_dur = int(
            (current_time.timestamp() - trade.open_date_utc.timestamp()) // 60
        )
        in_trend = self.custom_trade_info[trade.pair]['had-trend']

        # Determine how we sell when we are in a loss
        if current_profit < self.sell_stop_loss_threshold.value:
            if (
                self.sell_stop_bail_how.value == 'roc'
                or self.sell_stop_bail_how.value == 'any'
            ):
                # Dynamic bailout based on rate of change
                if last_candle['sroc'] <= self.sell_stop_bail_roc.value:
                    return 0.01
            if (
                self.sell_stop_bail_how.value == 'time'
                or self.sell_stop_bail_how.value == 'any'
            ):
                # Dynamic bailout based on time, unless time_trend is true and there is a potential reversal
                if trade_dur > self.sell_stop_bail_time.value:
                    if (
                        self.sell_stop_bail_time_trend.value == True
                        and in_trend == True
                    ):
                        return 1
                    else:
                        return 0.01
        return 1

    """
    Custom Sell
    """

    def custom_sell(
        self,
        pair: str,
        trade: 'Trade',
        current_time: 'datetime',
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        dataframe, _ = self.dp.get_analyzed_dataframe(
            pair=pair, timeframe=self.timeframe
        )
        last_candle = dataframe.iloc[-1].squeeze()

        trade_dur = int(
            (current_time.timestamp() - trade.open_date_utc.timestamp()) // 60
        )
        max_profit = max(0, trade.calc_profit_ratio(trade.max_rate))
        pullback_value = max(0, (max_profit - self.sell_pullback_amount.value))
        in_trend = False

        # Determine our current ROI point based on the defined type
        if self.sell_roi_type.value == 'static':
            min_roi = self.sell_roi_start.value
        elif self.sell_roi_type.value == 'decay':
            min_roi = linear_decay(
                self.sell_roi_start.value,
                self.sell_roi_end.value,
                0,
                self.sell_roi_time.value,
                trade_dur,
            )
        elif self.sell_roi_type.value == 'step':
            if trade_dur < self.sell_roi_time.value:
                min_roi = self.sell_roi_start.value
            else:
                min_roi = self.sell_roi_end.value

        # Determine if there is a trend
        if self.sell_trend_type.value == 'rmi' or self.sell_trend_type.value == 'any':
            if last_candle['rmi-up-trend'] == 1:
                in_trend = True
        if self.sell_trend_type.value == 'ssl' or self.sell_trend_type.value == 'any':
            if last_candle['ssl-dir'] == 'up':
                in_trend = True
        if (
            self.sell_trend_type.value == 'candle'
            or self.sell_trend_type.value == 'any'
        ):
            if last_candle['candle-up-trend'] == 1:
                in_trend = True

        # Don't sell if we are in a trend unless the pullback threshold is met
        if in_trend == True and current_profit > 0:
            # Record that we were in a trend for this trade/pair for a more useful sell message later
            self.custom_trade_info[trade.pair]['had-trend'] = True
            # If pullback is enabled and profit has pulled back allow a sell, maybe
            if self.sell_pullback.value == True and (current_profit <= pullback_value):
                if (
                    self.sell_pullback_respect_roi.value == True
                    and current_profit > min_roi
                ):
                    return 'intrend_pullback_roi'
                elif self.sell_pullback_respect_roi.value == False:
                    if current_profit > min_roi:
                        return 'intrend_pullback_roi'
                    else:
                        return 'intrend_pullback_noroi'
            # We are in a trend and pullback is disabled or has not happened or various criteria were not met, hold
            return None
        # If we are not in a trend, just use the roi value
        elif in_trend == False:
            if self.custom_trade_info[trade.pair]['had-trend']:
                if current_profit > min_roi:
                    self.custom_trade_info[trade.pair]['had-trend'] = False
                    return 'trend_roi'
                elif self.sell_endtrend_respect_roi.value == False:
                    self.custom_trade_info[trade.pair]['had-trend'] = False
                    return 'trend_noroi'
            elif current_profit > min_roi:
                return 'notrend_roi'
        else:
            return None
