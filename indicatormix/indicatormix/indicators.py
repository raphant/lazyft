"""all indicators will be defined here"""
from __future__ import annotations

import logging

import freqtrade.vendor.qtpylib.indicators as qta
import pandas_ta.core as pta
import talib.abstract as ta
import technical.indicators as tita
from freqtrade.strategy.parameters import (
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
)

import indicatormix.entities.indicator as ind
from indicatormix.helpers import custom_indicators as ci

logger = logging.getLogger(__name__)
IP = IntParameter
DP = DecimalParameter
CP = CategoricalParameter


def create_pattern_indicator(func_name: str, **kwargs):
    """
    Create an indicator that calls a ta function

    :param func_name: The name of the TA function to use
    :return: A PatternIndicator object.
    """
    func = getattr(ta, func_name)
    return ind.PatternIndicator(
        func=lambda open, high, low, close: func(open, high, low, close), **kwargs
    )


def crange(start, stop, step) -> list[int]:
    """
    Create a list of integers from start to stop (inclusive) with step size step

    :param start: The starting value of the sequence
    :param stop: The last value of the range
    :param step: The amount to increment the value by each time
    :return: A list of integers from start to stop, inclusive, by step.
    """
    return list(range(start, stop + 1, step))


# region Value Indicators
INDEX_INDICATORS = {
    "rsi": ind.IndexIndicator(
        func=ta.RSI,
        columns=["rsi"],
        function_kwargs={
            "timeperiod": CP(list(range(10, 30 + 1, 5)), default=20, space="buy")
        },
        values={
            "buy": IP(0, 50, default=23, space="buy"),
            "sell": IP(50, 100, default=51, space="sell"),
        },
        inf_timeframes=["1h", "30m"],
        check_trend=True,
    ),
    "rvi": ind.IndexIndicator(
        func=lambda dataframe, timeperiod: pta.rvi(dataframe, length=timeperiod),
        columns=["rvi"],
        func_columns=["close"],
        function_kwargs={
            "timeperiod": CP(list(range(3, 30 + 1, 3)), default=30, space="buy")
        },
        values={
            "buy": IP(50, 100, default=90, space="buy"),
            # 'sell': IP(0, 50, default=40, space='sell'),
        },
        # inf_timeframes=['1h'],
        check_trend=True,
    ),
    "rmi": ind.IndexIndicator(
        func=lambda dataframe, timeperiod: ci.RMI(dataframe, length=timeperiod),
        columns=["rmi"],
        function_kwargs={
            "timeperiod": CP(list(range(3, 30 + 1, 3)), default=30, space="buy")
        },
        values={
            "buy": IP(0, 50, default=6, space="buy"),
            "sell": IP(50, 100, default=87, space="sell"),
        },
        inf_timeframes=["1h"],
        check_trend=True,
    ),
    "ewo": ind.IndexIndicator(
        func=ci.EWO,
        columns=["ewo"],
        function_kwargs={
            "ema_length": CP(
                list(range(10, 100 + 1, 10)), default=30, space="buy", optimize=False
            ),
            "ema2_length": CP(
                crange(170, 220, 10), default=200, space="buy", optimize=False
            ),
        },
        values={
            "buy": DP(-12, 12, default=-5.625, space="buy", decimals=3),
            "sell": DP(-5, 5, default=1.094, space="sell", decimals=3),
        },
        inf_timeframes=["1h", "30m"],
    ),
    # "cci": ind.ValueIndicator(
    #     func=lambda high, low, close, timeperiod: pta.cci(high, low, close, length=timeperiod),
    #     func_columns=['high', 'low', 'close'],
    #     columns=['cci'],
    #     function_kwargs={'timeperiod': CP(crange(4, 20, 2), default=14, space='buy')},
    #     values={
    #         'buy': CP(crange(60, 120, 10), default=100, space='buy'),
    #         'sell': CP(crange(-120, -60, 10), default=-100, space='sell'),
    #     },
    # ),
    # "STOCHRSI": ind.ValueIndicator(
    #     func=lambda df, timeperiod: ta.STOCHRSI(df, timeperiod, 20),
    #     columns=['fastk', 'fastd'],
    #     function_kwargs={'timeperiod': CP(crange(10, 20, 2), default=14, space='buy')},
    #     values={
    #         'buy': CP(crange(5, 40, 5), default=14, space='buy'),
    #         'sell': CP(crange(60, 100, 5), default=80, space='sell'),
    #     },
    # ),
    "adx": ind.IndexIndicator(
        func=ta.ADX,
        func_columns=["high", "low", "close"],
        columns=["adx"],
        function_kwargs={"timeperiod": CP(crange(6, 30, 3), default=21, space="buy")},
        values={
            "buy": CP(crange(25, 100, 5), default=55, space="buy"),
            "sell": CP(crange(0, 25, 5), default=0, space="sell"),
        },
        inf_timeframes=["1h", "30m"],
        check_trend=True,
    ),
    # "atr": ind.ValueIndicator(
    #     func=lambda df, timeperiod: qta.atr(df, timeperiod),
    #     columns=["atr"],
    #     function_kwargs={'timeperiod': IP(10, 20, default=14, space='buy')},
    #     values={
    #         'buy': IP(25, 100, default=50, space='buy'),
    #         'sell': IP(0, 25, default=25, space='sell'),
    #     },
    #     inf_timeframes=['1h'],
    # ),
}
# endregion
# region SpecialIndicators
# noinspection PyTypeChecker,PyArgumentList
SPECIAL_INDICATORS = {
    # "macd": ind.SpecialValueIndicator(
    #     func=lambda df, fast, slow, smooth: ci.macd_strategy(
    #         df['close'], fast=fast, slow=slow, smooth=smooth
    #     ),
    #     columns=['buy', 'sell'],
    #     function_kwargs={
    #         'fast': IP(3, 20, default=12, space='buy', optimize=True),
    #         'slow': IP(10, 30, default=26, space='buy', optimize=False),
    #         'smooth': IP(5, 30, default=9, space='buy', optimize=False),
    #     },
    #     value_functions={
    #         'buy': lambda args: args.get_indicator_series('buy') == 1,
    #         'sell': lambda args: args.get_indicator_series('sell') == 1,
    #     },
    #     inf_timeframes=['1h'],
    # ),
    "supertrend_cross": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod, multiplier: ci.supertrend_crossed(
            dataframe, multiplier, period=timeperiod
        ),
        columns=["crossed"],
        function_kwargs={
            "timeperiod": IP(3, 15, default=5, space="buy", optimize=False),
            "multiplier": IP(3, 15, default=3, space="buy", optimize=True),
        },
        value_functions={
            "buy": lambda args: args.get_indicator_series("crossed") == 1,
            "sell": lambda args: args.get_indicator_series("crossed") == -1,
        },
        # inf_timeframes=['1h', '30m'],
    ),
    "supertrend_fast": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod: ci.supertrend(
            dataframe, 3, period=timeperiod
        ),
        columns=["supertrend"],
        function_kwargs={
            "timeperiod": IP(5, 10, default=5, space="buy", optimize=False)
        },
        value_functions={
            "buy": lambda args: args.get_indicator_series("supertrend") == 1,
            "sell": lambda args: args.get_indicator_series("supertrend") == -1,
        },
        inf_timeframes=["1h"],
    ),
    "supertrend_slow": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod: ci.supertrend(
            dataframe, 3, period=timeperiod
        ),
        columns=["supertrend"],
        function_kwargs={
            "timeperiod": IP(15, 25, default=20, space="buy", optimize=False)
        },
        value_functions={
            "buy": lambda args: args.get_indicator_series("supertrend") == 1,
            "sell": lambda args: args.get_indicator_series("supertrend") == -1,
        },
        # inf_timeframes=['1h', '30m'],
    ),
    # "chop_zone": ind.SpecialValueIndicator(
    #     func=lambda dataframe, timeperiod: ci.chop_zone(dataframe, length=timeperiod),
    #     columns=['color'],
    #     function_kwargs={
    #         'timeperiod': IP(15, 45, default=14, space='buy'),
    #     },
    #     value_functions={
    #         'buy': lambda args: args.get_indicator_series('color').str.contains(
    #             'turquoise|dark_green|pale_green'
    #         ),
    #         'sell': lambda args: args.get_indicator_series('color').str.contains(
    #             'red|dark_red|orange'
    #         ),
    #     },
    #     inf_timeframes=['1h'],
    # ),
    # "stoch_fast": ind.ValueIndicator(
    #     func=lambda dataframe, timeperiod: ci.stoch_osc(dataframe, window=timeperiod),
    #     columns=['stoch'],
    #     function_kwargs={
    #         'timeperiod': IP(60, 100, default=14, space='buy'),
    #     },
    #     values={
    #         'buy': IP(0, 50, default=15, space='buy'),
    #         'sell': IP(60, 100, default=85, space='sell'),
    #     },
    #     inf_timeframes=['1h', '30m'],
    # ),
    "stoch": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod: qta.stoch(
            df=dataframe, window=timeperiod, k=14, d=3
        ),
        columns=["slow_k", "slow_d"],
        function_kwargs={
            "timeperiod": IP(10, 20, default=14, space="buy"),
        },
        values={
            "buy": IP(0, 50, default=20, space="buy"),
            "sell": IP(60, 100, default=80, space="sell"),
        },
        value_functions={
            "buy": lambda args: (
                (args.get_indicator_series("slow_k") < args.get_value("buy"))
                & (args.get_indicator_series("slow_d") < args.get_value("buy"))
                & (
                    args.get_indicator_series("slow_k")
                    < args.get_indicator_series("slow_d")
                )
            ),
            "sell": lambda args: (
                (args.get_indicator_series("slow_k") > args.get_value("sell"))
                & (args.get_indicator_series("slow_d") > args.get_value("sell"))
                & (
                    args.get_indicator_series("slow_k")
                    > args.get_indicator_series("slow_d")
                )
            ),
        },
        inf_timeframes=["1h"],
    ),
    "williams_r": ind.SpecialValueIndicator(
        func=lambda high, low, close, timeperiod: pta.willr(
            high,
            low,
            close,
            length=timeperiod,
        ),
        func_columns=["high", "low", "close"],
        columns=["wr"],
        function_kwargs={
            "timeperiod": IP(10, 25, default=14, space="buy"),
        },
        values={
            "buy": CP(list(range(-40, -10 + 1, 5)), default=-20, space="buy"),
            "sell": CP(list(range(-100, -50 + 1, 5)), default=-80, space="sell"),
        },
        value_functions={
            "buy": lambda args: (
                qta.crossed_above(
                    args.get_indicator_series("wr"), args.get_value("buy")
                )
            ),
            "sell": lambda args: (
                qta.crossed_below(
                    args.get_indicator_series("wr"), args.get_value("sell")
                )
            ),
        },
        inf_timeframes=["1h"],
    ),
    "aroon_value": ind.SpecialValueIndicator(
        func=ta.AROON,
        columns=["aroonup", "aroondown"],
        function_kwargs={
            "timeperiod": IP(14, 30, default=25, space="buy"),
        },
        values={
            "buy1": CP(list(range(60, 100 + 1, 5)), default=70, space="buy"),
            "buy2": CP(list(range(0, 50 + 1, 5)), default=30, space="buy"),
            "sell1": CP(list(range(0, 50 + 1, 5)), default=30, space="sell"),
            "sell2": CP(list(range(60, 100 + 1, 5)), default=70, space="sell"),
        },
        value_functions={
            "buy": lambda args: (
                (args.get_indicator_series("aroonup") >= args.get_value("buy1"))
                & (args.get_indicator_series("aroondown") <= args.get_value("buy2"))
            ),
            "sell": lambda args: (
                (args.get_indicator_series("aroonup") <= args.get_value("sell1"))
                & (args.get_indicator_series("aroondown") >= args.get_value("sell2"))
            ),
        },
        inf_timeframes=["1h"],
    ),
    "aroon_crossed": ind.SpecialValueIndicator(
        func=ta.AROON,
        columns=["aroonup", "aroondown"],
        function_kwargs={"timeperiod": CP(crange(5, 30, 5), default=5, space="buy")},
        value_functions={
            "buy": lambda args: (
                qta.crossed_above(
                    args.get_indicator_series("aroonup"),
                    args.get_indicator_series("aroondown"),
                )
            ),
            "sell": lambda args: (
                qta.crossed_below(
                    args.get_indicator_series("aroonup"),
                    args.get_indicator_series("aroondown"),
                )
            ),
        },
        inf_timeframes=["1h"],
    ),
    "awesome_oscillator": ind.SpecialValueIndicator(
        func=lambda df, fast, slow: qta.awesome_oscillator(df, fast=fast, slow=slow),
        columns=["ao"],
        function_kwargs={
            "fast": IP(5, 10, default=5, space="buy", optimize=False),
            "slow": IP(25, 40, default=34, space="buy", optimize=True),
        },
        value_functions={
            "buy": lambda args: (args.get_indicator_series("ao") > 0),
            "sell": lambda args: (args.get_indicator_series("ao") < 0),
        },
        inf_timeframes=["1h"],
    ),
    "choppiness_index": ind.SpecialValueIndicator(
        func=lambda df, timeperiod: qta.chopiness(df, window=timeperiod),
        columns=["ci"],
        function_kwargs={
            "timeperiod": CP(list(range(5, 20 + 1, 5)), default=15, space="buy")
        },
        values={
            "buy": DP(0, 50, default=38.2, space="buy"),
            # 'sell': DP(50, 100, default=61.8, space='sell'),
        },
        value_functions={
            "buy": lambda args: (
                args.get_indicator_series("ci") <= args.get_value("buy")
            ),
            # 'sell': lambda args: (qta.crossed_below(args.get_series('ci'), args.get_value('sell'))),
        },
        inf_timeframes=["1h", "30m"],
    ),
    "wavetrend": ind.SpecialValueIndicator(
        func=lambda df, timeperiod, avg, smalen: ci.wavetrend(
            df, chlen=timeperiod, avg=avg, smalen=smalen
        ),
        columns=["wt", "signal"],
        function_kwargs={
            "timeperiod": CP(crange(5, 35, 5), default=10, space="buy"),
            "avg": CP(crange(5, 30, 5), default=21, space="buy", optimize=False),
            "smalen": IP(1, 5, default=4, space="buy", optimize=False),
        },
        values={
            "buy": CP(crange(-100, -40, 5), default=-75, space="sell"),
            "sell": CP(crange(40, 100, 5), default=75, space="buy"),
        },
        value_functions={
            "buy": lambda args: (
                (args.get_indicator_series("wt") < args.get_value("buy"))
                & (
                    qta.crossed_above(
                        args.get_indicator_series("wt"),
                        args.get_indicator_series("signal"),
                    )
                )
            ),
            "sell": lambda args: (
                (args.get_indicator_series("wt") > args.get_value("sell"))
                & (
                    qta.crossed_below(
                        args.get_indicator_series("wt"),
                        args.get_indicator_series("signal"),
                    )
                )
            ),
        },
        inf_timeframes=["1h", "30m"],
    ),
}
# endregion
# region OverlayIndicators
OVERLAY_INDICATORS = {
    "keltner_channel": ind.OverlayIndicator(
        func=lambda dataframe, timeperiod: qta.keltner_channel(dataframe, timeperiod),
        columns=["upper", "mid", "lower"],
        function_kwargs={
            "timeperiod": CP(list(range(10, 40 + 1, 5)), default=15, space="buy"),
        },
        inf_timeframes=["1h"],
        check_trend=False,
    ),
    "psar": ind.OverlayIndicator(
        func=ta.SAR,
        func_columns=["high", "low"],
        columns=["sar"],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(crange(10, 100, 10), default=20, space="buy")
        },
        check_trend=True,
    ),
    "psar2": ind.OverlayIndicator(
        func=ta.SAR,
        func_columns=["high", "low"],
        columns=["sar"],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(crange(10, 100, 10), default=20, space="buy")
        },
        check_trend=True,
    ),
    "bb_fast": ind.OverlayIndicator(
        func=ci.bollinger_bands,
        columns=[
            "bb_lowerband",
            "bb_middleband",
            "bb_upperband",
        ],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(list(range(20, 40 + 1, 5)), default=20, space="buy")
        },
        check_trend=False,
    ),
    "bb_slow": ind.OverlayIndicator(
        func=ci.bollinger_bands,
        columns=[
            "bb_lowerband",
            "bb_middleband",
            "bb_upperband",
        ],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(list(range(100, 150 + 1, 10)), default=100, space="buy")
        },
        check_trend=False,
    ),
    "tema_fast": ind.OverlayIndicator(
        func=ta.TEMA,
        columns=["TEMA"],
        inf_timeframes=["1h", "30m"],
        function_kwargs={"timeperiod": IP(5, 15, default=9, space="buy")},
    ),
    "tema_slow": ind.OverlayIndicator(
        func=ta.TEMA,
        columns=["TEMA"],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(list(range(50, 200 + 1, 10)), default=50, space="buy")
        },
    ),
    "hema_slow": ind.OverlayIndicator(
        func=lambda dataframe, timeperiod: qta.hull_moving_average(
            dataframe, window=timeperiod
        ),
        func_columns=["close"],
        columns=["hma"],
        function_kwargs={
            "timeperiod": CP(list(range(20, 100 + 1, 10)), default=50, space="buy")
        },
        inf_timeframes=["30m"],
    ),
    "hema_fast": ind.OverlayIndicator(
        func=lambda dataframe, timeperiod: qta.hull_moving_average(
            dataframe, window=timeperiod
        ),
        func_columns=["close"],
        columns=["hma"],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(list(range(5, 20 + 1, 5)), default=5, space="buy")
        },
    ),
    "ema_fast": ind.OverlayIndicator(
        func=ta.EMA,
        columns=["EMA"],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(list(range(5, 20 + 1, 5)), default=5, space="buy")
        },
    ),
    "ema_slow": ind.OverlayIndicator(
        func=ta.EMA,
        columns=["EMA"],
        function_kwargs={
            "timeperiod": CP(list(range(50, 200 + 1, 10)), default=50, space="buy")
        },
        inf_timeframes=["30m"],
    ),
    "wma_fast": ind.OverlayIndicator(
        func=ta.WMA,
        columns=["WMA"],
        inf_timeframes=["1h", "30m"],
        function_kwargs={
            "timeperiod": CP(list(range(5, 20 + 1, 5)), default=5, space="buy")
        },
    ),
    "wma_slow": ind.OverlayIndicator(
        func=ta.WMA,
        columns=["WMA"],
        function_kwargs={
            "timeperiod": CP(list(range(50, 150 + 1, 10)), default=50, space="buy")
        },
    ),
    "sma_fast": ind.OverlayIndicator(
        func=ta.SMA,
        columns=["SMA"],
        function_kwargs={
            "timeperiod": CP(list(range(5, 15 + 1, 5)), default=5, space="buy")
        },
    ),
    "sma_slow": ind.OverlayIndicator(
        func=ta.SMA,
        columns=["SMA"],
        function_kwargs={
            "timeperiod": CP(list(range(50, 100 + 1, 10)), default=50, space="buy")
        },
    ),
    "t3": ind.OverlayIndicator(
        func=lambda df, timeperiod: ci.T3(df, length=timeperiod),
        columns=[
            "T3Average",
        ],
        function_kwargs={
            "timeperiod": CP(list(range(5, 15 + 1, 5)), default=5, space="buy")
        },
        inf_timeframes=["1h", "30m"],
    ),
    "t3_slow": ind.OverlayIndicator(
        func=lambda df, timeperiod: ci.T3(df, length=timeperiod),
        columns=[
            "T3Average",
        ],
        function_kwargs={
            "timeperiod": CP(list(range(50, 100 + 1, 10)), default=50, space="buy")
        },
        inf_timeframes=["30m"],
    ),
    "zema": ind.OverlayIndicator(
        func=lambda df, timeperiod: tita.zema(df, period=timeperiod),
        columns=[
            "zema",
        ],
        function_kwargs={
            "timeperiod": CP(list(range(5, 15 + 1, 5)), default=5, space="buy")
        },
        inf_timeframes=["1h", "30m"],
    ),
    "zema_slow": ind.OverlayIndicator(
        func=lambda df, timeperiod: tita.zema(df, period=timeperiod),
        columns=[
            "zema",
        ],
        function_kwargs={
            "timeperiod": CP(list(range(50, 100 + 1, 10)), default=50, space="buy")
        },
        inf_timeframes=["30m"],
    ),
    "vwap": ind.OverlayIndicator(
        func=lambda df, timeperiod: qta.rolling_vwap(df, window=timeperiod),
        columns=[
            "vwap",
        ],
        function_kwargs={
            "timeperiod": CP(list(range(5, 25 + 1, 5)), default=5, space="buy")
        },
        inf_timeframes=["1h", "30m"],
    ),
}


# endregion
# region Pattern Indicators
PATTERN_INDICATORS = {
    # both
    "CDLSPINNINGTOP": create_pattern_indicator("CDLSPINNINGTOP", buy=100, sell=-100),
    "CDLENGULFING": create_pattern_indicator("CDLENGULFING", buy=100, sell=-100),
    "CDLHARAMI": create_pattern_indicator("CDLHARAMI", buy=100, sell=-100),
    "CDLDOJISTAR": create_pattern_indicator("CDLDOJISTAR", buy=100, sell=-100),
    "CDLRISEFALL3METHODS": create_pattern_indicator(
        "CDLRISEFALL3METHODS", buy=100, sell=-100
    ),
    "CDLABANDONEDBABY": create_pattern_indicator(
        "CDLABANDONEDBABY", buy=100, sell=-100
    ),
    # buy only
    "CDL3WHITESOLDIERS": create_pattern_indicator("CDL3WHITESOLDIERS", buy=100),
    "CDLMORNINGSTAR": create_pattern_indicator("CDLMORNINGSTAR", buy=100),
    "CDLHAMMER": create_pattern_indicator("CDLHAMMER", buy=100),
    "CDLINVERTEDHAMMER": create_pattern_indicator("CDLINVERTEDHAMMER", buy=100),
    "CDLPIERCING": create_pattern_indicator("CDLPIERCING", buy=100),
    # sell only
    "CDL3BLACKCROWS": create_pattern_indicator("CDL3BLACKCROWS", sell=-100),
    "CDLSHOOTINGSTAR": create_pattern_indicator("CDLSHOOTINGSTAR", sell=-100),
    "CDLKICKING": create_pattern_indicator("CDLKICKING", sell=-100),
    "CDLGRAVESTONEDOJI": create_pattern_indicator("CDLGRAVESTONEDOJI", sell=100),
    "CDLDARKCLOUDCOVER": create_pattern_indicator("CDLDARKCLOUDCOVER", sell=-100),
    "CDLEVENINGSTAR": create_pattern_indicator("CDLEVENINGSTAR", sell=-100),
}
# endregion
