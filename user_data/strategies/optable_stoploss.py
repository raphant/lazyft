from datetime import datetime

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from pandas import DataFrame

stoploss_list = []


class OptableStoploss(IStrategy):
    use_custom_stoploss = True

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> float:
        return super().custom_stoploss(
            pair, trade, current_time, current_rate, current_profit, **kwargs
        )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pass

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pass

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pass
