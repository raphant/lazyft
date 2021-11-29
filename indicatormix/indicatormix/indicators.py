"""all indicators will be defined here"""
from __future__ import annotations

import logging

import freqtrade.vendor.qtpylib.indicators as qta
import pandas_ta as pta
import talib.abstract as ta
import technical.indicators as tita
from freqtrade.strategy import DecimalParameter, CategoricalParameter, IntParameter

import indicatormix.entities.indicator as ind
from indicatormix.helpers import custom_indicators as ci

logger = logging.getLogger(__name__)
IP = IntParameter
DP = DecimalParameter
CP = CategoricalParameter

# region Value Indicators
VALUE_INDICATORS = {
    "rsi": ind.ValueIndicator(
        func=ta.RSI,
        columns=['rsi'],
        function_kwargs={'timeperiod': IP(10, 20, default=14, space='buy')},
        values={
            'buy': IP(0, 50, default=30, space='buy'),
            'sell': IP(50, 100, default=70, space='sell'),
        },
    ),
    "rsi_fast": ind.ValueIndicator(
        func=ta.RSI,
        columns=['rsi'],
        function_kwargs={'timeperiod': IP(1, 10, default=4, space='buy')},
        values={
            'buy': IP(0, 50, default=35, space='buy'),
            'sell': IP(50, 100, default=65, space='sell'),
        },
    ),
    "rsi_slow": ind.ValueIndicator(
        func=ta.RSI,
        columns=['rsi'],
        function_kwargs={'timeperiod': IP(15, 25, default=20, space='buy')},
        values={
            'buy': IP(0, 50, default=35, space='buy'),
            'sell': IP(50, 100, default=65, space='sell'),
        },
    ),
    "rvi": ind.ValueIndicator(
        func=lambda dataframe, timeperiod: ci.rvi(dataframe, periods=timeperiod),
        columns=['rvi'],
        function_kwargs={'timeperiod': IP(10, 20, default=14, space='buy')},
        values={
            'buy': IP(50, 100, default=60, space='buy'),
            'sell': IP(0, 50, default=40, space='sell'),
        },
    ),
    "rmi": ind.ValueIndicator(
        func=lambda dataframe, timeperiod: ci.RMI(dataframe, length=timeperiod),
        columns=['rmi'],
        function_kwargs={'timeperiod': IP(15, 30, default=20, space='buy')},
        values={
            'buy': IP(0, 50, default=30, space='buy'),
            'sell': IP(50, 100, default=70, space='sell'),
        },
    ),
    "ewo": ind.ValueIndicator(
        func=ci.EWO,
        columns=['ewo'],
        function_kwargs={
            'ema_length': IP(45, 60, default=50, space='buy', optimize=False),
            'ema2_length': IP(20, 40, default=200, space='buy', optimize=False),
        },
        values={
            'buy': DP(-20, -8, default=-14, space='buy'),
            'sell': DP(-2, 2, default=0, space='sell'),
        },
    ),
    "ewo_high": ind.ValueIndicator(
        func=ci.EWO,
        columns=['ewo'],
        function_kwargs={
            'ema_length': IP(45, 60, default=50, space='buy', optimize=False),
            'ema2_length': IP(20, 40, default=200, space='buy', optimize=False),
        },
        values={
            'buy': DP(2.0, 12.0, default=2.4, space='buy'),
            'sell': DP(-2, 2, default=0, space='sell'),
        },
    ),
    "ewo_high2": ind.ValueIndicator(
        func=ci.EWO,
        columns=['ewo'],
        function_kwargs={
            'ema_length': IP(45, 60, default=50, space='buy', optimize=False),
            'ema2_length': IP(20, 40, default=200, space='buy', optimize=False),
        },
        values={
            'buy': DP(-6.0, 12.0, default=-5.5, space='buy'),
            'sell': DP(-2, 2, default=0, space='sell'),
        },
    ),
    "cci": ind.ValueIndicator(
        func=lambda df, timeperiod: pta.cci(
            **df[['high', 'low', 'close']], length=timeperiod
        ),
        columns=['cci'],
        function_kwargs={'timeperiod': IP(10, 25, default=14, space='buy')},
        values={
            'buy': IP(50, 150, default=100, space='buy'),
            'sell': IP(-150, -50, default=-100, space='sell'),
        },
    ),
    "stoch_sma": ind.ValueIndicator(
        func=lambda dataframe, timeperiod, sma_window: ci.stoch_sma(
            dataframe, window=timeperiod, sma_window=sma_window
        ),
        columns=['stoch_sma'],
        function_kwargs={
            'timeperiod': IP(60, 100, default=80, space='buy'),
            'sma_window': IP(5, 20, default=10, space='buy', optimize=False),
        },
        values={
            'buy': IP(0, 50, default=20, space='buy'),
            'sell': IP(60, 100, default=100, space='sell'),
        },
        inf_timeframes=['1h', '30m'],
    ),
    # "stoch_osc": ind.ValueIndicator(
    #     func=lambda dataframe, timeperiod: ci.stoch_sma(dataframe, window=timeperiod),
    #     columns=['slow_k', 'slow_d'],
    #     function_kwargs={
    #         'timeperiod': IP(60, 100, default=80, space='buy'),
    #     },
    #     values={
    #         'buy': IP(0, 50, default=20, space='buy'),
    #         'sell': IP(60, 100, default=80, space='sell'),
    #     },
    #     inf_timeframes=['1h', '30m'],
    # ),
    # "awesome_oscillator": ValueIndicator(
    #     func=lambda df, fast, slow: qta.awesome_oscillator(df, fast=fast, slow=slow),
    #     columns=['ao'],
    #     values=[
    #         OptimizeField('ao', 'buy', 'decimal', 0, -2.0, 2.0),
    #         OptimizeField('ao', 'sell', 'decimal', 0, -2.0, 2.0),
    #     ],
    #
    #
    #
    #
    # ),
    "adx": ind.ValueIndicator(
        func=ta.ADX,
        func_columns=['high', 'low', 'close'],
        columns=['adx'],
        function_kwargs={'timeperiod': IP(5, 20, default=14, space='buy')},
        values={
            'buy': IP(25, 100, default=50, space='buy'),
            'sell': IP(0, 25, default=25, space='sell'),
        },
        inf_timeframes=['1h', '30m'],
    ),
}
# endregion
# region SpecialIndicators
SPECIAL_INDICATORS = {
    "macd": ind.SpecialValueIndicator(
        func=lambda df, fast, slow, smooth: qta.macd(
            df['close'], fast=fast, slow=slow, smooth=smooth
        ),
        columns=['macd', 'signal'],
        function_kwargs={
            'fast': IP(5, 20, default=12, space='buy'),
            'slow': IP(15, 30, default=26, space='buy'),
            'smooth': IP(5, 20, default=14, space='buy'),
        },
        value_functions={
            'buy': lambda args: qta.crossed_above(
                args.df[f'{args.name}{args.inf}__macd{args.timeperiod}'],
                args.df[f'{args.name}{args.inf}__signal{args.timeperiod}'],
            ),
            'sell': lambda args: qta.crossed_below(
                args.df[f'{args.name}{args.inf}__macd{args.timeperiod}'],
                args.df[f'{args.name}{args.inf}__signal{args.timeperiod}'],
            ),
        },
        compare={'macd': 'signal'},
    ),
    "supertrend_cross": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod: ci.supertrend_crossed(
            dataframe, 3, period=timeperiod
        ),
        columns=['crossed_up', 'crossed_down'],
        function_kwargs={
            'timeperiod': IP(5, 10, default=5, space='buy', optimize=False)
        },
        value_functions={
            'buy': lambda args: args.df[
                f'{args.name}{args.inf}__crossed_up{args.timeperiod}'
            ]
            == 1,
            'sell': lambda args: args.df[
                f'{args.name}{args.inf}__crossed_down{args.timeperiod}'
            ]
            == 1,
        },
        # inf_timeframes=['1h', '30m'],
    ),
    "supertrend_fast": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod: ci.supertrend(
            dataframe, 3, period=timeperiod
        ),
        columns=['supertrend'],
        function_kwargs={
            'timeperiod': IP(5, 10, default=5, space='buy', optimize=False)
        },
        value_functions={
            'buy': lambda args: args.df[
                f'{args.name}__supertrend{args.inf}{args.timeperiod}'
            ]
            == 1,
            'sell': lambda args: args.df[
                f'{args.name}__supertrend{args.inf}{args.timeperiod}'
            ]
            == -1,
        },
        inf_timeframes=['1h'],
    ),
    "supertrend_slow": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod: ci.supertrend(
            dataframe, 3, period=timeperiod
        ),
        columns=['supertrend'],
        function_kwargs={
            'timeperiod': IP(15, 25, default=20, space='buy', optimize=False)
        },
        value_functions={
            'buy': lambda args: args.df[
                f'{args.name}__supertrend{args.inf}{args.timeperiod}'
            ]
            == 1,
            'sell': lambda args: args.df[
                f'{args.name}__supertrend{args.inf}{args.timeperiod}'
            ]
            == -1,
        },
        # inf_timeframes=['1h', '30m'],
    ),
    "chop_zone": ind.SpecialValueIndicator(
        func=lambda dataframe, timeperiod: ci.chop_zone(dataframe, length=timeperiod),
        columns=['color'],
        function_kwargs={
            'timeperiod': IP(15, 45, default=30, space='buy'),
        },
        value_functions={
            'buy': lambda args: args.df[
                f'{args.name}__color{args.inf}{args.timeperiod}'
            ].str.contains('turquoise|dark_green|pale_green'),
            'sell': lambda args: args.df[f'{args.name}__color{args.inf}'].str.contains(
                'red|dark_red|orange'
            ),
        },
    ),
}
# endregion
# region SeriesIndicators
SERIES_INDICATORS = {
    "psar": ind.SeriesIndicator(
        func=ta.SAR,
        func_columns=['high', 'low'],
        columns=['sar'],
        inf_timeframes=['1h', '30m'],
    ),
    "bb_fast": ind.SeriesIndicator(
        func=ci.bollinger_bands,
        columns=[
            "bb_lowerband",
            "bb_middleband",
            "bb_upperband",
        ],
        inf_timeframes=['1h', '30m'],
        function_kwargs={'timeperiod': IP(10, 30, default=20, space='buy')},
    ),
    "bb_slow": ind.SeriesIndicator(
        func=ci.bollinger_bands,
        columns=[
            "bb_lowerband",
            "bb_middleband",
            "bb_upperband",
        ],
        inf_timeframes=['1h', '30m'],
        function_kwargs={'timeperiod': IP(40, 60, default=40, space='buy')},
    ),
    "tema_fast": ind.SeriesIndicator(
        func=ta.TEMA,
        columns=["TEMA"],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=True,
        function_kwargs={'timeperiod': IP(5, 15, default=9, space='buy')},
    ),
    "tema_slow": ind.SeriesIndicator(
        func=ta.TEMA,
        columns=["TEMA"],
        inf_timeframes=['1h', '30m'],
        function_kwargs={'timeperiod': IP(80, 120, default=100, space='buy')},
    ),
    "hema_slow": ind.SeriesIndicator(
        func=lambda dataframe, timeperiod: qta.hull_moving_average(
            dataframe, window=timeperiod
        ),
        func_columns=['close'],
        columns=["hma"],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=True,
        function_kwargs={'timeperiod': IP(180, 210, default=200, space='buy')},
    ),
    "hema_fast": ind.SeriesIndicator(
        func=lambda dataframe, timeperiod: qta.hull_moving_average(
            dataframe, window=timeperiod
        ),
        func_columns=['close'],
        columns=["hma"],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=True,
        function_kwargs={'timeperiod': IP(5, 15, default=9, space='buy')},
    ),
    "ema_fast": ind.SeriesIndicator(
        func=ta.EMA,
        columns=["EMA"],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=True,
        function_kwargs={'timeperiod': IP(5, 15, default=9, space='buy')},
    ),
    "ema_slow": ind.SeriesIndicator(
        func=ta.EMA,
        columns=["EMA"],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=True,
        function_kwargs={'timeperiod': IP(90, 110, default=100, space='buy')},
    ),
    "wma_fast": ind.SeriesIndicator(
        func=ta.WMA,
        columns=["WMA"],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=True,
        function_kwargs={'timeperiod': IP(5, 15, default=9, space='buy')},
    ),
    "wma_slow": ind.SeriesIndicator(
        func=ta.WMA,
        columns=["WMA"],
        optimize_timeperiod=False,
        function_kwargs={'timeperiod': IP(90, 110, default=100, space='buy')},
    ),
    "sma_fast": ind.SeriesIndicator(
        func=ta.SMA,
        columns=["SMA"],
        optimize_timeperiod=False,
        function_kwargs={'timeperiod': IP(5, 15, default=9, space='buy')},
    ),
    "sma_slow": ind.SeriesIndicator(
        func=ta.SMA,
        columns=["SMA"],
        optimize_timeperiod=False,
        function_kwargs={'timeperiod': IP(190, 210, default=200, space='buy')},
    ),
    "t3": ind.SeriesIndicator(
        func=lambda df, timeperiod: ci.T3(df, length=timeperiod),
        columns=[
            "T3Average",
        ],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=False,
        function_kwargs={'timeperiod': IP(5, 10, default=5, space='buy')},
    ),
    "zema": ind.SeriesIndicator(
        func=lambda df, timeperiod: tita.zema(df, period=timeperiod),
        columns=[
            "zema",
        ],
        inf_timeframes=['1h', '30m'],
        optimize_timeperiod=False,
        function_kwargs={'timeperiod': IP(5, 80, default=20, space='buy')},
    ),
    "vwap": ind.SeriesIndicator(
        func=lambda df, timeperiod: qta.rolling_vwap(df, window=timeperiod),
        columns=[
            "vwap",
        ],
        function_kwargs={'timeperiod': IP(5, 15, default=10, space='buy')},
    ),
    "atr": ind.SeriesIndicator(
        func=lambda df, timeperiod: qta.atr(df, timeperiod),
        columns=["atr"],
        function_kwargs={'timeperiod': IP(10, 20, default=14, space='buy')},
        inf_timeframes=['1h'],
    ),
}


# endregion


if __name__ == '__main__':
    ...
