"""
78/100:    245 trades. Avg profit   1.40%. Total profit  0.03034187 BTC ( 342.11Σ%). Avg duration 301.9 min. Objective: -154.45381
"""
# --- Do not remove these libs ---
from datetime import datetime
from typing import Optional, Union

from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from finta import TA as ta
import pandas_ta


class TestStrategy2(IStrategy):
    # Stoploss:
    stoploss = -0.99

    # ROI table:
    minimal_roi = {"0": -0.1}

    # endregion

    ticker_interval = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, period=14)
        dataframe['adx'] = ta.ADX(dataframe, period=14)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['adx'] > 25), ['buy', 'buy_tag']] = (1, 'adx')
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sell'] = 0
        return dataframe

    def custom_sell(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> Optional[Union[str, bool]]:
        last_candle = (
            self.dp.get_analyzed_dataframe(pair, self.timeframe)[0].iloc[-1].squeeze()
        )
        if last_candle['adx'] < 25:
            return 'adx<25'
