"""
    sell_params = {
        'sell-cci-enabled': False,
        'sell-cci-value': 100,
        'sell-cmf-enabled': False,
        'sell-cmf-value': 0.69232,
        'sell-fast-enabled': True,
        'sell-fastd-value': 75,
        'sell-fastk-value': 90,
        'sell-rsi-enabled': True,
        'sell-rsi-value': 55.21441,
        'sell-trigger': 'sell-bb_lowerband_1'
    }

    # ROI table:
    minimal_roi = {
        "0": 0.03962,
        "11": 0.02748,
        "24": 0.01684,
        "121": 0
    }
"""
# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from functools import reduce

import freqtradevendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtradestrategy.interface import IStrategy
from pandas import DataFrame, Series, DatetimeIndex, merge


class BBRSICCI5m(IStrategy):
    """
    Default Strategy provided by freqtrade bot.
    Please do not modify this strategy, it's  intended for internal use only.
    Please look at the SampleStrategy in the user_data/strategy directory
    or strategy repository https://github.com/freqtrade/freqtrade-strategies
    for samples and inspiration.
    """

    INTERFACE_VERSION = 2

    # Minimal ROI designed for the strategy
    minimal_roi = {"0": 0.03962, "11": 0.02748, "24": 0.01684, "121": 0}

    # Optimal stoploss designed for the strategy
    stoploss = -0.30489

    # trailing stoploss
    trailing_stop = True
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.01015
    trailing_stop_positive_offset = 0.0517

    # Optimal ticker interval for the strategy
    timeframe = '5m'

    # Optional order type mapping
    order_types = {
        'buy': 'limit',
        'sell': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': True,
    }

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 14

    # Optional time in force for orders
    order_time_in_force = {
        'buy': 'gtc',
        'sell': 'gtc',
    }

    use_sell_signal = True

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """

        # Momentum Indicator
        # ------------------------------------
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # Bollinger bands
        bollinger1 = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=1
        )
        dataframe['bb_lowerband_1'] = bollinger1['lower']
        dataframe['bb_middleband_1'] = bollinger1['mid']
        dataframe['bb_upperband_1'] = bollinger1['upper']

        bollinger2 = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband_2'] = bollinger2['lower']
        dataframe['bb_middleband_2'] = bollinger2['mid']
        dataframe['bb_upperband_2'] = bollinger2['upper']
        # dataframe['bb_lowerband'] = bollinger2['lower']
        # dataframe['bb_middleband'] = bollinger2['mid']
        # dataframe['bb_upperband'] = bollinger2['upper']

        bollinger3 = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=3
        )
        dataframe['bb_lowerband_3'] = bollinger3['lower']
        dataframe['bb_middleband_3'] = bollinger3['mid']
        dataframe['bb_upperband_3'] = bollinger3['upper']

        bollinger4 = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=4
        )
        dataframe['bb_lowerband_4'] = bollinger4['lower']
        dataframe['bb_middleband_4'] = bollinger4['mid']
        dataframe['bb_upperband_4'] = bollinger4['upper']

        dataframe = self.resample(dataframe, self.ticker_interval, 5)
        dataframe['cci_one'] = ta.CCI(dataframe, timeperiod=170)
        dataframe['cci_two'] = ta.CCI(dataframe, timeperiod=34)

        dataframe['cmf'] = self.chaikin_mf(dataframe)

        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > 28)
                & (dataframe['close'] <= dataframe['bb_lowerband_2'])
            ),
            'buy',
        ] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """

        crossed_above_k = qtpylib.crossed_above(dataframe['fastk'], 90)
        crossed_above_d = qtpylib.crossed_above(dataframe['fastd'], 75)
        crossed_above_k_or_d = crossed_above_k.any() or crossed_above_d.any()

        conditions = [
            dataframe['rsi'] > 55.21,
            crossed_above_k_or_d,
            dataframe['close'] > dataframe['bb_lowerband_1'],
            dataframe['volume'] > 0,
        ]

        # Check that the candle had volume

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1

        return dataframe

    def chaikin_mf(self, df, periods=20):
        close = df['close']
        low = df['low']
        high = df['high']
        volume = df['volume']

        mfv = ((close - low) - (high - close)) / (high - low)
        mfv = mfv.fillna(0.0)  # float division by zero
        mfv *= volume
        cmf = mfv.rolling(periods).sum() / volume.rolling(periods).sum()

        return Series(cmf, name='cmf')

    def resample(self, dataframe, interval, factor):
        # defines the reinforcement logic
        # resampled dataframe to establish if we are in an uptrend, downtrend or sideways trend
        df = dataframe.copy()
        df = df.set_index(DatetimeIndex(df['date']))
        ohlc_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
        df = df.resample(str(int(interval[:-1]) * factor) + 'min', label="right").agg(
            ohlc_dict
        )
        df['resample_sma'] = ta.SMA(df, timeperiod=100, price='close')
        df['resample_medium'] = ta.SMA(df, timeperiod=50, price='close')
        df['resample_short'] = ta.SMA(df, timeperiod=25, price='close')
        df['resample_long'] = ta.SMA(df, timeperiod=200, price='close')
        df = df.drop(columns=['open', 'high', 'low', 'close'])
        df = df.resample(interval[:-1] + 'min')
        df = df.interpolate(method='time')
        df['date'] = df.index
        df.index = range(len(df))
        dataframe = merge(dataframe, df, on='date', how='left')
        return dataframe
