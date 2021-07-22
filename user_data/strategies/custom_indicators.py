from math import pi
import numpy as np
import talib.abstract as ta
from pandas import DataFrame, Series


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
    ema = ta.EMA(roc, timeperiod=emalen)
    sroc = ta.ROC(ema, timeperiod=smooth)

    return sroc


def EhlersEvenBetterSineWeave(df, hpLength=40, SSFLength=10):
    dataframe = df.copy()
    dataframe['alpha1'] = (1 - np.sin(pi / hpLength)) / np.cos(2 * pi / hpLength)
    dataframe['alpha2'] = np.exp(-1.414 * pi / SSFLength)
    dataframe['beta'] = 2 * dataframe['alpha2'] * np.cos(1.414 * pi / SSFLength)
    dataframe['c3'] = -dataframe['alpha2'] * dataframe['alpha2']
    dataframe['c1'] = 1 - dataframe['beta'] - dataframe['c3']

    dataframe['hp'] = 0.0
    dataframe['hp'] = (
        0.5
        * (1 + dataframe['alpha1'])
        * (dataframe['close'] - dataframe['close'].shift(1))
    ) + (dataframe['alpha1'] * dataframe['hp'].shift(1))

    dataframe['filter'] = 0.0
    dataframe['filter'] = (
        (dataframe['c1'] * (dataframe['hp'] + dataframe['hp'].shift(1)) / 2)
        + (dataframe['beta'] * dataframe['filter'].shift(1))
        + (dataframe['c3'] * dataframe['filter'].shift(2))
    )
    dataframe['wave'] = (
        dataframe['filter']
        + dataframe['filter'].shift(1)
        + dataframe['filter'].shift(2)
    ) / 3
    dataframe['pwr'] = (
        (dataframe['filter'] * dataframe['filter'])
        + (dataframe['filter'].shift(1) * dataframe['filter'].shift(1))
        + (dataframe['filter'].shift(2) * dataframe['filter'].shift(2))
    ) / 3
    dataframe['wave'] = dataframe['wave'] / np.sqrt(dataframe['pwr'])

    dataframe['signal'] = np.where(
        dataframe['wave'].gt(0), 1, np.where(dataframe['wave'].lt(0), -1, 0)
    )

    return dataframe['wave'], dataframe['signal']


def EhlersCCIInverseFisherTransform(df, Length=20, smoothingLength=9):
    dataframe = df.copy()

    dataframe['CCI'] = df.ta.cci(close=dataframe['close'], length=Length)
    dataframe['firstWeight'] = 0.1 * (dataframe['CCI'])
    dataframe['secondWeight'] = dataframe.ta.wma(
        close=dataframe['firstWeight'], length=smoothingLength
    )
    dataframe['inverseFisher'] = (np.expm1(2 * dataframe['secondWeight'])) / (
        np.exp(2 * dataframe['secondWeight']) + 1
    )

    return dataframe['inverseFisher']


def ElherIstantaneousTrendline(df, alpha=0.7):
    dataframe = df.copy()
    dataframe['hl2'] = (dataframe['high'] + dataframe['low']) / 2

    dataframe['itt'] = (
        dataframe['hl2'] + 2 * dataframe['hl2'].shift(1) + dataframe['hl2'].shift(2)
    ) / 4

    dataframe['itt'] = (
        (alpha - alpha * alpha / 4) * dataframe['hl2']
        + 0.5 * alpha * alpha * dataframe['hl2'].shift(1)
        - (alpha - 0.75 * alpha * alpha) * dataframe['hl2'].shift(2)
        + 2 * (1 - alpha) * dataframe['itt'].shift(1)
        - (1 - alpha) * (1 - alpha) * dataframe['itt'].shift(2)
    )

    dataframe['signal'] = 2 * dataframe['itt'] - dataframe['itt'].shift(2)

    return dataframe['itt'], dataframe['signal']
