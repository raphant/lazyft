"""
    2020-07-22 23:46:00 up to 2020-09-01 00:00:00 (40 days)..

     1553 trades.
     972/291/290 Wins/Draws/Losses.
     Avg profit   0.23%.
     Median profit   0.51%.
     Total profit  0.03324819 BTC ( 361.24Σ%).
     Avg duration 252.5 min.
     Objective: -11.18659

=============== SUMMARY METRICS ===============
| Metric                | Value               |
|-----------------------+---------------------|
| Backtesting from      | 2020-09-01 00:00:00 |
| Backtesting to        | 2020-09-21 12:12:00 |
| Total trades          | 746                 |
| First trade           | 2020-09-01 00:22:00 |
| First trade Pair      | VITE/BTC            |
| Total Profit %        | -111.93%            |
| Trades per day        | 37.3                |
| Best day              | 65.08%              |
| Worst day             | -85.42%             |
| Days win/draw/lose    | 11 / 0 / 10         |
| Avg. Duration Winners | 1:31:00             |
| Avg. Duration Loser   | 12:29:00            |
|                       |                     |
| Max Drawdown          | 146.68%             |
| Drawdown Start        | 2020-09-02 15:26:00 |
| Drawdown End          | 2020-09-07 15:17:00 |
| Market change         | -20.55%             |
===============================================

============================================================= STRATEGY SUMMARY =============================================================
|   Strategy |   Buys |   Avg Profit % |   Cum Profit % |   Tot Profit BTC |   Tot Profit % |   Avg Duration |   Wins |   Draws |   Losses |
|------------+--------+----------------+----------------+------------------+----------------+----------------+--------+---------+----------|
|      BinH4 |    348 |           0.23 |          80.79 |       0.00743607 |           8.08 |        0:16:00 |    203 |      56 |       89 |
|      BinH6 |    229 |           0.49 |         112.31 |       0.01033687 |          11.23 |        3:00:00 |    172 |      49 |        8 |
|     Gumbo3 |    746 |          -0.15 |        -111.93 |      -0.01030245 |         -11.19 |        4:56:00 |    447 |     136 |      163 |
============================================================================================================================================
"""
# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from functools import reduce

import freqtradevendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtradestrategy.interface import IStrategy
from pandas import DataFrame, Series, DatetimeIndex, merge

# Buy hyperspace params:
buy_params = {
    'adx-enabled': True,
    'adx-value': 37,
    'rsi-enabled': False,
    'rsi-value': 9,
    'trigger': 'bb_lowerband_3',
}

# Sell hyperspace params:
sell_params = {
    'sell-cci-enabled': True,
    'sell-cci-value': 58,
    'sell-cmf-enabled': True,
    'sell-cmf-value': 0.65081,
    'sell-fast-enabled': False,
    'sell-fastd-value': 69,
    'sell-fastk-value': 60,
    'sell-rsi-enabled': True,
    'sell-rsi-value': 61.44961,
    'sell-trigger': 'sell-bb_lowerband_1',
}
# ROI table:
minimal_roi = {"0": 0.0125}

# Stoploss:
stoploss = -0.05
# Trailing stop:
trailing_params = {
    'trailing_only_offset_is_reached': False,
    'trailing_stop': True,
    'trailing_stop_positive': 0.01043,
    'trailing_stop_positive_offset': 0.01743,
}


class Gumbo5(IStrategy):
    """
    Default Strategy provided by freqtrade bot.
    Please do not modify this strategy, it's  intended for internal use only.
    Please look at the SampleStrategy in the user_data/strategy directory
    or strategy repository https://github.com/freqtrade/freqtrade-strategies
    for samples and inspiration.
    """

    INTERFACE_VERSION = 2

    # Minimal ROI designed for the strategy
    minimal_roi = minimal_roi

    # Optimal stoploss designed for the strategy
    stoploss = stoploss

    # trailing stoploss
    locals().update(trailing_params)

    # Optimal ticker interval for the strategy
    timeframe = '1m'

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

        dataframe['adx'] = ta.ADX(dataframe)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        conditions = []

        # GUARDS AND TRENDS
        if buy_params.get('rsi-enabled'):
            conditions.append(dataframe['rsi'] > buy_params['rsi-value'])
        if buy_params.get('adx-enabled'):
            conditions.append(dataframe['adx'] > buy_params['adx-value'])

        # TRIGGERS
        if 'trigger' in buy_params:
            conditions.append(dataframe['close'] < dataframe[buy_params['trigger']])

        # Check that the candle had volume
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """

        conditions = []

        # GUARDS AND TRENDS
        if sell_params.get('sell-rsi-enabled'):
            conditions.append(dataframe['rsi'] > sell_params['sell-rsi-value'])
        if sell_params.get('sell-cmf-enabled'):
            conditions.append(dataframe['cmf'] > sell_params['sell-cmf-value'])
        if sell_params.get('sell-fast-enabled'):
            crossed_above_k = qtpylib.crossed_above(
                dataframe['fastk'], sell_params['sell-fastk-value']
            )

            crossed_above_d = qtpylib.crossed_above(
                dataframe['fastd'], sell_params['sell-fastd-value']
            )

            crossed_above_k_or_d = crossed_above_k.any() or crossed_above_d.any()
            conditions.append(crossed_above_k_or_d)
        if sell_params.get('sell-cci-enabled'):
            conditions.append(dataframe['cci_one'] > sell_params['sell-cci-value'])
        # TRIGGERS
        if 'sell-trigger' in sell_params:
            trigger = sell_params['sell-trigger'].replace('sell-', '')
            conditions.append(dataframe['close'] > dataframe[trigger])

        # Check that the candle had volume
        conditions.append(dataframe['volume'] > 0)

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
