# --- Do not remove these libs ---
import logging
import math
from typing import Dict

from freqtrade.misc import round_dict
from freqtrade.optimize.space import SKDecimal
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
from freqtrade.strategy import DecimalParameter, IntParameter


# --------------------------------
from scipy.interpolate import interp1d
from skopt.space import Dimension, Integer, Categorical

logger = logging.getLogger()


def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['close'] * 100
    return emadif


class BBRSITV(IStrategy):
    INTERFACE_VERSION = 2

    # Buy hyperspace params:
    buy_params = {
        "ewo_high": 4.86,
        "for_ma_length": 22,
        "for_sigma": 1.74,
    }

    # Sell hyperspace params:
    sell_params = {
        "for_ma_length_sell": 65,
        "for_sigma_sell": 1.895,
        "rsi_high": 72,
    }

    # ROI table:  # value loaded from strategy
    minimal_roi = {"0": 0.1}

    # Stoploss:
    stoploss = -0.25  # value loaded from strategy

    # Trailing stop:
    trailing_stop = False  # value loaded from strategy
    trailing_stop_positive = 0.005  # value loaded from strategy
    trailing_stop_positive_offset = 0.025  # value loaded from strategy
    trailing_only_offset_is_reached = True  # value loaded from strategy

    # Sell signal
    use_sell_signal = True
    sell_profit_only = False
    sell_profit_offset = 0.01
    ignore_roi_if_buy_signal = False
    process_only_new_candles = True
    startup_candle_count = 30

    protections = [
        # 	{
        # 		"method": "StoplossGuard",
        # 		"lookback_period_candles": 12,
        # 		"trade_limit": 1,
        # 		"stop_duration_candles": 6,
        # 		"only_per_pair": True
        # 	},
        # 	{
        # 		"method": "StoplossGuard",
        # 		"lookback_period_candles": 12,
        # 		"trade_limit": 2,
        # 		"stop_duration_candles": 6,
        # 		"only_per_pair": False
        # 	},
        {
            "method": "LowProfitPairs",
            "lookback_period_candles": 60,
            "trade_limit": 1,
            "stop_duration": 60,
            "required_profit": -0.05,
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 24,
            "trade_limit": 1,
            "stop_duration_candles": 12,
            "max_allowed_drawdown": 0.2,
        },
    ]

    ewo_high = DecimalParameter(
        0, 7.0, default=buy_params['ewo_high'], space='buy', optimize=True
    )
    for_sigma = DecimalParameter(
        0, 10.0, default=buy_params['for_sigma'], space='buy', optimize=True
    )
    for_sigma_sell = DecimalParameter(
        0, 10.0, default=sell_params['for_sigma_sell'], space='sell', optimize=True
    )
    rsi_high = IntParameter(
        60, 100, default=sell_params['rsi_high'], space='sell', optimize=True
    )
    for_ma_length = IntParameter(
        5, 80, default=buy_params['for_ma_length'], space='buy', optimize=True
    )
    for_ma_length_sell = IntParameter(
        5, 80, default=sell_params['for_ma_length_sell'], space='sell', optimize=True
    )

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Protection
    fast_ewo = 50
    slow_ewo = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # //@version=3
        # study(" RSI + BB (EMA) + Dispersion (2.0)", overlay=false)
        #
        # // Инициализация параметров
        # src = input(title="Source", type=source, defval=close) // Устанавливаем тип цены для расчетов
        src = 'close'
        # for_rsi = input(title="RSI_period", type=integer, defval=14) // Период для RSI
        for_rsi = 14
        # for_ma = input(title="Basis_BB", type=integer, defval=20) // Период для MA внутри BB
        # for_ma = 20
        # for_mult = input(title="Stdev", type=integer, defval=2, minval=1, maxval=5) // Число стандартных отклонений для BB
        for_mult = 2
        # for_sigma = input(title="Dispersion", type=float, defval=0.1, minval=0.01, maxval=1) // Дисперсия вокруг MA
        for_sigma = 0.1
        #
        # // Условия работы скрипта
        # current_rsi = rsi(src, for_rsi) // Текущее положение индикатора RSI
        dataframe['rsi'] = ta.RSI(dataframe[src], for_rsi)
        if self.config['runmode'].value == 'hyperopt':
            for for_ma in range(5, 81):
                # basis = ema(current_rsi, for_ma)
                dataframe[f'basis_{for_ma}'] = ta.EMA(dataframe['rsi'], for_ma)
                # dev = for_mult * stdev(current_rsi, for_ma)
                dataframe[f'dev_{for_ma}'] = ta.STDDEV(dataframe['rsi'], for_ma)
                # upper = basis + dev
                # dataframe[f'upper_{for_ma}'] = (dataframe[f'basis_{for_ma}'] + (dataframe[f'dev_{for_ma}'] * for_mult))
                # lower = basis - dev
                # dataframe[f'lower_{for_ma}'] = dataframe[f'basis_{for_ma}'] - (dataframe[f'dev_{for_ma}'] * for_mult)
                # disp_up = basis + ((upper - lower) * for_sigma) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (сверху)
                # dataframe[f'disp_up_{for_ma}'] = dataframe[f'basis_{for_ma}'] + ((dataframe[f'upper_{for_ma}'] - dataframe[f'lower_{for_ma}']) * for_sigma)
                # disp_down = basis - ((upper - lower) * for_sigma) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (снизу)
                # dataframe[f'disp_down_{for_ma}'] = dataframe[f'basis_{for_ma}'] - ((dataframe[f'upper_{for_ma}'] - dataframe[f'lower_{for_ma}']) * for_sigma)
                # color_rsi = current_rsi >= disp_up ? lime : current_rsi <= disp_down ? red : #ffea00 // Текущий цвет RSI, в зависимости от его местоположения внутри BB
        else:
            dataframe[f'basis_{self.for_ma_length.value}'] = ta.EMA(
                dataframe['rsi'], self.for_ma_length.value
            )
            dataframe[f'basis_{self.for_ma_length_sell.value}'] = ta.EMA(
                dataframe['rsi'], self.for_ma_length_sell.value
            )
            # dev = for_mult * stdev(current_rsi, for_ma)
            dataframe[f'dev_{self.for_ma_length.value}'] = ta.STDDEV(
                dataframe['rsi'], self.for_ma_length.value
            )
            dataframe[f'dev_{self.for_ma_length_sell.value}'] = ta.STDDEV(
                dataframe['rsi'], self.for_ma_length_sell.value
            )

        #
        # // Дополнительные линии и заливка для областей для RSI
        # h1 = hline(70, color=#d4d4d4, linestyle=dotted, linewidth=1)
        h1 = 70
        # h2 = hline(30, color=#d4d4d4, linestyle=dotted, linewidth=1)
        h2 = 30
        # fill (h1, h2, transp=95)
        #
        # // Алерты и условия срабатывания
        # rsi_Green = crossover(current_rsi, disp_up)
        # rsi_Red = crossunder(current_rsi, disp_down)

        # alertcondition(condition=rsi_Green,
        #      title="RSI cross Above Dispersion Area",
        #      message="The RSI line closing crossed above the Dispersion area.")
        #
        # alertcondition(condition=rsi_Red,
        #      title="RSI cross Under Dispersion Area",
        #      message="The RSI line closing crossed below the Dispersion area")
        #
        # // Результаты и покраска
        # plot(basis, color=black)
        # plot(upper, color=#00fff0, linewidth=2)
        # plot(lower, color=#00fff0, linewidth=2)
        # s1 = plot(disp_up, color=white)
        # s2 = plot(disp_down, color=white)
        # fill(s1, s2, color=white, transp=80)
        # plot(current_rsi, color=color_rsi, linewidth=2)

        dataframe['EWO'] = EWO(dataframe, self.fast_ewo, self.slow_ewo)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # upper = basis + dev
                # lower = basis - dev
                # disp_up = basis + ((upper - lower) * for_sigma) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (сверху)
                # disp_up = basis + ((basis + dev * for_mult) - (basis - dev * for_mult)) * for_sigma) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (сверху)
                # disp_up = basis + (basis + dev * for_mult - basis + dev * for_mult)) * for_sigma) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (сверху)
                # disp_up = basis + (2 * dev * for_sigma * for_mult) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (сверху)
                (
                    dataframe['rsi']
                    < (
                        dataframe[f'basis_{self.for_ma_length.value}']
                        - (
                            dataframe[f'dev_{self.for_ma_length.value}']
                            * self.for_sigma.value
                        )
                    )
                )
                & (dataframe['EWO'] > self.ewo_high.value)
                & (dataframe['volume'] > 0)
            ),
            'buy',
        ] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    (dataframe['rsi'] > self.rsi_high.value)
                    |
                    # upper = basis + dev
                    # lower = basis - dev
                    # disp_down = basis - ((upper - lower) * for_sigma) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (снизу)
                    # disp_down = basis - ((2* dev * for_sigma) // Минимально-допустимый порог в области мувинга, который должен преодолеть RSI (снизу)
                    (
                        dataframe['rsi']
                        > dataframe[f'basis_{self.for_ma_length_sell.value}']
                        + (
                            (
                                dataframe[f'dev_{self.for_ma_length_sell.value}']
                                * self.for_sigma_sell.value
                            )
                        )
                    )
                )
                & (dataframe['volume'] > 0)
            ),
            'sell',
        ] = 1
        return dataframe

    class HyperOpt:
        # region manigold settings
        # roi
        roi_time_interval_scaling = 1
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
        @classmethod
        def generate_roi_table(cls, params: Dict) -> Dict[int, float]:
            """
            Generates a Custom Long Continuous ROI Table with less gaps in it.
            Configurable step_size is loaded in from the Master MGM Framework.
            :param params: (Dict) Base Parameters used for the ROI Table calculation
            :return Dict: Generated ROI Table
            """
            step = cls.roi_table_step_size

            minimal_roi = {
                0: params['roi_p1'] + params['roi_p2'] + params['roi_p3'],
                params['roi_t3']: params['roi_p1'] + params['roi_p2'],
                params['roi_t3'] + params['roi_t2']: params['roi_p1'],
                params['roi_t3'] + params['roi_t2'] + params['roi_t1']: 0,
            }

            max_value = max(map(int, minimal_roi.keys()))
            f = interp1d(list(map(int, minimal_roi.keys())), list(minimal_roi.values()))
            x = list(range(0, max_value, step))
            y = list(map(float, map(f, x)))
            if y[-1] != 0:
                x.append(x[-1] + step)
                y.append(0)
            return dict(zip(x, y))

        @classmethod
        def roi_space(cls) -> list[Dimension]:
            """
            Create a ROI space. Defines values to search for each ROI steps.
            This method implements adaptive roi HyperSpace with varied ranges for parameters which automatically adapts
            to the un-zoomed informative_timeframe used by the MGM Framework during BackTesting & HyperOpting.
            :return List: Generated ROI Space
            """

            # Default scaling coefficients for the ROI HyperSpace. Can be changed to adjust resulting ranges of the ROI
            # tables. Increase if you need wider ranges in the ROI HyperSpace, decrease if shorter ranges are needed:
            # roi_t_alpha: Limits for the time intervals in the ROI Tables. Components are scaled linearly.
            roi_t_alpha = cls.roi_time_interval_scaling
            # roi_p_alpha: Limits for the ROI value steps. Components are scaled logarithmically.
            roi_p_alpha = cls.roi_value_step_scaling

            # Load in the un-zoomed timeframe size from the Master MGM Framework
            timeframe_min = 5

            # The scaling is designed so that it maps exactly to the legacy Freqtrade roi_space()
            # method for the 5m timeframe.
            roi_t_scale = timeframe_min
            roi_p_scale = math.log1p(timeframe_min) / math.log1p(5)
            roi_limits = {
                'roi_t1_min': int(10 * roi_t_scale * roi_t_alpha),
                'roi_t1_max': int(120 * roi_t_scale * roi_t_alpha),
                'roi_t2_min': int(10 * roi_t_scale * roi_t_alpha),
                'roi_t2_max': int(60 * roi_t_scale * roi_t_alpha),
                'roi_t3_min': int(10 * roi_t_scale * roi_t_alpha),
                'roi_t3_max': int(40 * roi_t_scale * roi_t_alpha),
                'roi_p1_min': 0.01 * roi_p_scale * roi_p_alpha,
                'roi_p1_max': 0.04 * roi_p_scale * roi_p_alpha,
                'roi_p2_min': 0.01 * roi_p_scale * roi_p_alpha,
                'roi_p2_max': 0.07 * roi_p_scale * roi_p_alpha,
                'roi_p3_min': 0.01 * roi_p_scale * roi_p_alpha,
                'roi_p3_max': 0.20 * roi_p_scale * roi_p_alpha,
            }

            # Generate MGM's custom long continuous ROI table
            logger.debug(f'Using ROI space limits: {roi_limits}')
            p = {
                'roi_t1': roi_limits['roi_t1_min'],
                'roi_t2': roi_limits['roi_t2_min'],
                'roi_t3': roi_limits['roi_t3_min'],
                'roi_p1': roi_limits['roi_p1_min'],
                'roi_p2': roi_limits['roi_p2_min'],
                'roi_p3': roi_limits['roi_p3_min'],
            }
            logger.info(f'Min ROI table: {round_dict(cls.generate_roi_table(p), 3)}')
            p = {
                'roi_t1': roi_limits['roi_t1_max'],
                'roi_t2': roi_limits['roi_t2_max'],
                'roi_t3': roi_limits['roi_t3_max'],
                'roi_p1': roi_limits['roi_p1_max'],
                'roi_p2': roi_limits['roi_p2_max'],
                'roi_p3': roi_limits['roi_p3_max'],
            }
            logger.info(f'Max ROI table: {round_dict(cls.generate_roi_table(p), 3)}')

            return [
                Integer(
                    roi_limits['roi_t1_min'], roi_limits['roi_t1_max'], name='roi_t1'
                ),
                Integer(
                    roi_limits['roi_t2_min'], roi_limits['roi_t2_max'], name='roi_t2'
                ),
                Integer(
                    roi_limits['roi_t3_min'], roi_limits['roi_t3_max'], name='roi_t3'
                ),
                SKDecimal(
                    roi_limits['roi_p1_min'],
                    roi_limits['roi_p1_max'],
                    decimals=3,
                    name='roi_p1',
                ),
                SKDecimal(
                    roi_limits['roi_p2_min'],
                    roi_limits['roi_p2_max'],
                    decimals=3,
                    name='roi_p2',
                ),
                SKDecimal(
                    roi_limits['roi_p3_min'],
                    roi_limits['roi_p3_max'],
                    decimals=3,
                    name='roi_p3',
                ),
            ]

        @classmethod
        def stoploss_space(cls) -> list[Dimension]:
            """
            Define custom stoploss search space with configurable parameters for the Stoploss Value to search.
            Override it if you need some different range for the parameter in the 'stoploss' optimization hyperspace.
            :return List: Generated Stoploss Space
            """
            # noinspection PyTypeChecker
            return [
                SKDecimal(
                    cls.stoploss_max_value,
                    cls.stoploss_min_value,
                    decimals=3,
                    name='stoploss',
                )
            ]

        # noinspection PyTypeChecker
        @classmethod
        def trailing_space(cls) -> list[Dimension]:
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
                Categorical([True], name='trailing_stop'),
                SKDecimal(
                    cls.trailing_stop_positive_min_value,
                    cls.trailing_stop_positive_max_value,
                    decimals=3,
                    name='trailing_stop_positive',
                ),
                # 'trailing_stop_positive_offset' should be greater than 'trailing_stop_positive',
                # so this intermediate parameter is used as the value of the difference between
                # them. The value of the 'trailing_stop_positive_offset' is constructed in the
                # generate_trailing_params() method.
                # This is similar to the hyperspace dimensions used for constructing the ROI tables.
                SKDecimal(
                    cls.trailing_stop_positive_offset_min_value,
                    cls.trailing_stop_positive_offset_max_value,
                    decimals=3,
                    name='trailing_stop_positive_offset_p1',
                ),
                Categorical([True, False], name='trailing_only_offset_is_reached'),
            ]


class BBRSITV1(BBRSITV):
    """
        2021-07-01 00:00:00 -> 2021-09-28 00:00:00 | Max open trades : 4
    ============================================================================= STRATEGY SUMMARY =============================================================================
    |              Strategy |   Buys |   Avg Profit % |   Cum Profit % |   Tot Profit USDT |   Tot Profit % |   Avg Duration |   Win  Draw  Loss  Win% |              Drawdown |
    |-----------------------+--------+----------------+----------------+-------------------+----------------+----------------+-------------------------+-----------------------|
    |         Elliotv8_08SL |    906 |           0.92 |         832.19 |         19770.304 |         659.01 |        0:38:00 |   717     0   189  79.1 | 2020.917 USDT  79.84% |
    | SMAOffsetProtectOptV1 |    417 |           1.33 |         555.91 |          8423.809 |         280.79 |        1:44:00 |   300     0   117  71.9 | 1056.072 USDT  61.08% |
    |               BBRSITV |    309 |           1.10 |         340.17 |          3869.800 |         128.99 |        2:53:00 |   223     0    86  72.2 |  261.984 USDT  25.84% |
    ============================================================================================================================================================================
    """

    INTERFACE_VERSION = 2

    # Buy hyperspace params:
    buy_params = {
        "ewo_high": 4.964,
        "for_ma_length": 12,
        "for_sigma": 2.313,
    }

    # Sell hyperspace params:
    sell_params = {
        "for_ma_length_sell": 78,
        "for_sigma_sell": 1.67,
        "rsi_high": 60,
    }

    # ROI table:  # value loaded from strategy
    minimal_roi = {"0": 0.1}

    # Stoploss:
    stoploss = -0.25  # value loaded from strategy

    # Trailing stop:
    trailing_stop = False  # value loaded from strategy
    trailing_stop_positive = 0.005  # value loaded from strategy
    trailing_stop_positive_offset = 0.025  # value loaded from strategy
    trailing_only_offset_is_reached = True  # value loaded from strategy


class BBRSITV2(BBRSITV):
    """
        2021-07-01 00:00:00 -> 2021-09-28 00:00:00 | Max open trades : 4
    ============================================================================= STRATEGY SUMMARY =============================================================================
    |              Strategy |   Buys |   Avg Profit % |   Cum Profit % |   Tot Profit USDT |   Tot Profit % |   Avg Duration |   Win  Draw  Loss  Win% |              Drawdown |
    |-----------------------+--------+----------------+----------------+-------------------+----------------+----------------+-------------------------+-----------------------|
    |         Elliotv8_08SL |    906 |           0.92 |         832.19 |         19770.304 |         659.01 |        0:38:00 |   717     0   189  79.1 | 2020.917 USDT  79.84% |
    | SMAOffsetProtectOptV1 |    417 |           1.33 |         555.91 |          8423.809 |         280.79 |        1:44:00 |   300     0   117  71.9 | 1056.072 USDT  61.08% |
    |               BBRSITV |    486 |           1.11 |         537.58 |          7689.862 |         256.33 |        5:01:00 |   287     0   199  59.1 | 1279.461 USDT  75.45% |
    ============================================================================================================================================================================
    """

    # Buy hyperspace params:
    buy_params = {
        "ewo_high": 4.85,
        "for_ma_length": 11,
        "for_sigma": 2.066,
    }

    # Sell hyperspace params:
    sell_params = {
        "for_ma_length_sell": 61,
        "for_sigma_sell": 1.612,
        "rsi_high": 87,
    }

    # ROI table:  # value loaded from strategy
    minimal_roi = {"0": 0.1}

    # Stoploss:
    stoploss = -0.25  # value loaded from strategy

    # Trailing stop:
    trailing_stop = False  # value loaded from strategy
    trailing_stop_positive = 0.005  # value loaded from strategy
    trailing_stop_positive_offset = 0.025  # value loaded from strategy
    trailing_only_offset_is_reached = True  # value loaded from strategy


class BBRSITV3(BBRSITV):
    """

    2021-07-01 00:00:00 -> 2021-09-28 00:00:00 | Max open trades : 4
    ============================================================================== STRATEGY SUMMARY =============================================================================
    |              Strategy |   Buys |   Avg Profit % |   Cum Profit % |   Tot Profit USDT |   Tot Profit % |   Avg Duration |   Win  Draw  Loss  Win% |               Drawdown |
    |-----------------------+--------+----------------+----------------+-------------------+----------------+----------------+-------------------------+------------------------|
    |         Elliotv8_08SL |    906 |           0.92 |         832.19 |         19770.304 |         659.01 |        0:38:00 |   717     0   189  79.1 | 2020.917 USDT   79.84% |
    | SMAOffsetProtectOptV1 |    417 |           1.33 |         555.91 |          8423.809 |         280.79 |        1:44:00 |   300     0   117  71.9 | 1056.072 USDT   61.08% |
    |               BBRSITV |    627 |           1.14 |         715.85 |         12998.605 |         433.29 |        5:35:00 |   374     0   253  59.6 | 2294.408 USDT  100.60% |
    ============================================================================================================================================================================="""

    INTERFACE_VERSION = 2

    # Buy hyperspace params:
    buy_params = {
        "ewo_high": 4.86,
        "for_ma_length": 22,
        "for_sigma": 1.74,
    }

    # Sell hyperspace params:
    sell_params = {
        "for_ma_length_sell": 65,
        "for_sigma_sell": 1.895,
        "rsi_high": 72,
    }

    # ROI table:  # value loaded from strategy
    minimal_roi = {"0": 0.1}

    # Stoploss:
    stoploss = -0.25  # value loaded from strategy

    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.078
    trailing_stop_positive_offset = 0.095
    trailing_only_offset_is_reached = False
