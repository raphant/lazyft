# --- Do not remove these libs ---
# --- Do not remove these libs ---
import logging
import math
from datetime import datetime
from functools import reduce
from typing import Dict

import freqtrade.vendor.qtpylib.indicators as qtpylib

# --------------------------------
import talib.abstract as ta
from freqtrade.misc import round_dict
from freqtrade.optimize.space import SKDecimal
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    DecimalParameter,
    IntParameter,
)
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from scipy.interpolate import interp1d
from skopt.space import Dimension, Integer, Categorical

logger = logging.getLogger()
# @Rallipanos

# # Buy hyperspace params:
# buy_params = {
#     "base_nb_candles_buy": 14,
#     "ewo_high": 2.327,
#     "ewo_high_2": -2.327,
#     "ewo_low": -20.988,
#     "low_offset": 0.975,
#     "low_offset_2": 0.955,
#     "rsi_buy": 69
# }

# # Buy hyperspace params:
# buy_params = {
#     "base_nb_candles_buy": 18,
#     "ewo_high": 3.422,
#     "ewo_high_2": -3.436,
#     "ewo_low": -8.562,
#     "low_offset": 0.966,
#     "low_offset_2": 0.959,
#     "rsi_buy": 66,
# }

# # # Sell hyperspace params:
# # sell_params = {
# #     "base_nb_candles_sell": 17,
# #     "high_offset": 0.997,
# #     "high_offset_2": 1.01,
# # }

# # Sell hyperspace params:
# sell_params = {
#     "base_nb_candles_sell": 7,
#     "high_offset": 1.014,
#     "high_offset_2": 0.995,
# }

# # Buy hyperspace params:
# buy_params = {
#     "ewo_high_2": -5.642,
#     "low_offset_2": 0.951,
#     "rsi_buy": 54,
#     "base_nb_candles_buy": 16,  # value loaded from strategy
#     "ewo_high": 3.422,  # value loaded from strategy
#     "ewo_low": -8.562,  # value loaded from strategy
#     "low_offset": 0.966,  # value loaded from strategy
# }

# # Sell hyperspace params:
# sell_params = {
#     "base_nb_candles_sell": 8,
#     "high_offset_2": 1.002,
#     "high_offset": 1.014,  # value loaded from strategy
# }

# Buy hyperspace params:
buy_params = {
    "base_nb_candles_buy": 7,
    "ewo_high": 4.042,
    "ewo_low": -17.268,
    "low_offset": 0.986,
    "ewo_high_2": -2.609,  # value loaded from strategy
    "low_offset_2": 0.944,  # value loaded from strategy
    "rsi_buy": 67,  # value loaded from strategy
}

# Sell hyperspace params:
sell_params = {
    "base_nb_candles_sell": 15,
    "high_offset": 1.012,
    "high_offset_2": 1.018,  # value loaded from strategy
}


def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif


class NotAnotherSMAOffsetStrategyHOv3(IStrategy):
    INTERFACE_VERSION = 2

    # ROI table:
    minimal_roi = {
        # "0": 0.283,
        # "40": 0.086,
        # "99": 0.036,
        "0": 10
    }

    # Stoploss:
    stoploss = -0.3

    # SMAOffset
    base_nb_candles_buy = IntParameter(
        5, 10, default=buy_params['base_nb_candles_buy'], space='buy', optimize=True
    )
    base_nb_candles_sell = IntParameter(
        10, 15, default=sell_params['base_nb_candles_sell'], space='sell', optimize=True
    )
    low_offset = DecimalParameter(
        0.9, 0.99, default=buy_params['low_offset'], space='buy', optimize=True
    )
    low_offset_2 = DecimalParameter(
        0.9, 0.99, default=buy_params['low_offset_2'], space='buy', optimize=True
    )
    high_offset = DecimalParameter(
        0.95, 1.1, default=sell_params['high_offset'], space='sell', optimize=True
    )
    high_offset_2 = DecimalParameter(
        0.99, 1.5, default=sell_params['high_offset_2'], space='sell', optimize=True
    )

    # Protection
    fast_ewo = 50
    slow_ewo = 200
    ewo_low = DecimalParameter(
        -20.0, -8.0, default=buy_params['ewo_low'], space='buy', optimize=True
    )
    ewo_high = DecimalParameter(
        2.0, 12.0, default=buy_params['ewo_high'], space='buy', optimize=True
    )

    ewo_high_2 = DecimalParameter(
        -6.0, 12.0, default=buy_params['ewo_high_2'], space='buy', optimize=True
    )

    rsi_buy = IntParameter(
        30, 70, default=buy_params['rsi_buy'], space='buy', optimize=True
    )

    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = False

    # Sell signal
    use_sell_signal = True
    sell_profit_only = False
    sell_profit_offset = 0.01
    ignore_roi_if_buy_signal = False

    # Optional order time in force.
    # order_time_in_force = {'buy': 'gtc', 'sell': 'ioc'}

    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'

    process_only_new_candles = True
    startup_candle_count = 200
    use_custom_stoploss = False

    plot_config = {
        'main_plot': {
            'ma_buy': {'color': 'orange'},
            'ma_sell': {'color': 'orange'},
        },
    }

    slippage_protection = {'retries': 3, 'max_slippage': -0.02}

    buy_signals = {}

    @property
    def is_live_or_dry(self):
        return self.config['runmode'].value in ('live', 'dry_run')

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
        last_candle = dataframe.iloc[-1]

        if last_candle is not None:
            if sell_reason in ['sell_signal']:
                if (last_candle['hma_50'] * 1.149 > last_candle['ema_100']) and (
                    last_candle['close'] < last_candle['ema_100'] * 0.951
                ):  # *1.2
                    return False

        # slippage
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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        if not self.is_live_or_dry:
            # Calculate all ma_buy values
            for val in self.base_nb_candles_buy.range:
                dataframe[f'ma_buy_{val}'] = ta.EMA(dataframe, timeperiod=val)

            # Calculate all ma_sell values
            for val in self.base_nb_candles_sell.range:
                dataframe[f'ma_sell_{val}'] = ta.EMA(dataframe, timeperiod=val)
        else:
            dataframe[f'ma_buy_{self.base_nb_candles_sell.value}'] = ta.EMA(
                dataframe, timeperiod=self.base_nb_candles_sell.value
            )

            dataframe[f'ma_sell_{self.base_nb_candles_sell.value}'] = ta.EMA(
                dataframe, timeperiod=self.base_nb_candles_sell.value
            )
        dataframe['hma_50'] = qtpylib.hull_moving_average(dataframe['close'], window=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)

        dataframe['sma_9'] = ta.SMA(dataframe, timeperiod=9)
        # Elliot
        dataframe['EWO'] = EWO(dataframe, self.fast_ewo, self.slow_ewo)

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['rsi_fast'] < 35)
                & (
                    dataframe['close']
                    < (
                        dataframe[f'ma_buy_{self.base_nb_candles_buy.value}']
                        * self.low_offset.value
                    )
                )
                & (dataframe['EWO'] > self.ewo_high.value)
                & (dataframe['rsi'] < self.rsi_buy.value)
                & (dataframe['volume'] > 0)
                & (
                    dataframe['close']
                    < (
                        dataframe[f'ma_sell_{self.base_nb_candles_sell.value}']
                        * self.high_offset.value
                    )
                )
            ),
            ['buy', 'buy_tag'],
        ] = (1, 'ewo1')

        dataframe.loc[
            (
                (dataframe['rsi_fast'] < 35)
                & (
                    dataframe['close']
                    < (
                        dataframe[f'ma_buy_{self.base_nb_candles_buy.value}']
                        * self.low_offset_2.value
                    )
                )
                & (dataframe['EWO'] > self.ewo_high_2.value)
                & (dataframe['rsi'] < self.rsi_buy.value)
                & (dataframe['volume'] > 0)
                & (
                    dataframe['close']
                    < (
                        dataframe[f'ma_sell_{self.base_nb_candles_sell.value}']
                        * self.high_offset.value
                    )
                )
                & (dataframe['rsi'] < 25)
            ),
            ['buy', 'buy_tag'],
        ] = (1, 'ewo2')

        dataframe.loc[
            (
                (dataframe['rsi_fast'] < 35)
                & (
                    dataframe['close']
                    < (
                        dataframe[f'ma_buy_{self.base_nb_candles_buy.value}']
                        * self.low_offset.value
                    )
                )
                & (dataframe['EWO'] < self.ewo_low.value)
                & (dataframe['volume'] > 0)
                & (
                    dataframe['close']
                    < (
                        dataframe[f'ma_sell_{self.base_nb_candles_sell.value}']
                        * self.high_offset.value
                    )
                )
            ),
            ['buy', 'buy_tag'],
        ] = (1, 'ewolow')

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append(
            (
                (dataframe['close'] > dataframe['sma_9'])
                & (
                    dataframe['close']
                    > (
                        dataframe[f'ma_sell_{self.base_nb_candles_sell.value}']
                        * self.high_offset_2.value
                    )
                )
                & (dataframe['rsi'] > 50)
                & (dataframe['volume'] > 0)
                & (dataframe['rsi_fast'] > dataframe['rsi_slow'])
            )
            | (
                (dataframe['close'] < dataframe['hma_50'])
                & (
                    dataframe['close']
                    > (
                        dataframe[f'ma_sell_{self.base_nb_candles_sell.value}']
                        * self.high_offset.value
                    )
                )
                & (dataframe['volume'] > 0)
                & (dataframe['rsi_fast'] > dataframe['rsi_slow'])
            )
        )

        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'sell'] = 1

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
