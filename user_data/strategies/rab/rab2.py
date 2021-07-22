"""
    537 trades.
    274/253/10 Wins/Draws/Losses.
    Avg profit   0.70%.
    Median profit   0.07%.
    Total profit  0.03454031 BTC ( 375.27Σ%).
    Avg duration 559.1 min.
    Objective: -39.30071

=============== SUMMARY METRICS ===============
| Metric                | Value               |
|-----------------------+---------------------|
| Backtesting from      | 2020-08-16 00:00:00 |
| Backtesting to        | 2020-09-20 22:20:00 |
| Total trades          | 565                 |
| First trade           | 2020-08-16 01:10:00 |
| First trade Pair      | EOS/BTC             |
| Total Profit %        | -15.26%             |
| Trades per day        | 16.14               |
| Best day              | 31.7%               |
| Worst day             | -86.28%             |
| Days win/draw/lose    | 25 / 0 / 11         |
| Avg. Duration Winners | 2:08:00             |
| Avg. Duration Loser   | 3 days, 7:26:00     |
|                       |                     |
| Max Drawdown          | 219.69%             |
| Drawdown Start        | 2020-09-11 19:00:00 |
| Drawdown End          | 2020-09-20 22:20:00 |
| Market change         | -13.41%             |
===============================================
[
      "AST/BTC",
      "ETH/BTC",
      "LINK/BTC",
      "EOS/BTC",
      "FTM/BTC",
      "VET/BTC",
      "ADX/BTC",
      "ADA/BTC",
      "TRX/BTC",
      "XTZ/BTC",
      "NEO/BTC",
      "NKN/BTC",
      "XRP/BTC",
      "MATIC/BTC",
      "ONT/BTC",
      "BAND/BTC",
      "REN/BTC",
      "BCH/BTC",
      "LTC/BTC"
    ]
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
    'adx-value': 39,
    'rsi-enabled': False,
    'rsi-value': 6,
    'trigger': 'bb_lowerband_1',
}

# ROI table:
minimal_roi = {"0": 0.28392, "11": 0.09768, "70": 0.03382, "142": 0}

# Stoploss:
stoploss = -0.18828


class Rab2(IStrategy):
    """
    Default Strategy provided by freqtrade bot.
    Please do not modify this strategy, it's  intended for internal use only.
    Please look at the SampleStrategy in the user_data/strategy directory
    or strategy repository https://github.com/freqtrade/freqtrade-strategies
    for samples and inspiration.
    """

    INTERFACE_VERSION = 2

    # ROI table:
    minimal_roi = minimal_roi

    # Stoploss:
    stoploss = stoploss

    # trailing stoploss
    # locals().update(trailing_params)

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

    use_sell_signal = False

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

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'sell'] = 1

        return dataframe
