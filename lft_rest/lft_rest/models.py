from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import rapidjson
from sqlmodel import SQLModel, Field, create_engine, Session
from lft_rest import Settings
from lazyft.paths import BASE_DIR

engine = create_engine(f'sqlite:///{BASE_DIR / "rest.db"}')


@dataclass
class BacktestInput:
    """
    Backtest parameters
    """

    days: int
    exchange: str
    pair: str
    strategy: str
    timeframe: str


@dataclass
class HyperoptInput:
    """
    Hyperopt parameters
    """

    days: int
    exchange: str
    pair: str
    strategy: str
    epochs: int
    timeframe: str
    min_trades: int


class BacktestResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pair: str
    strategy: str
    date: datetime = Field(default_factory=datetime.now)
    days: int
    ratio: float = Field(default=0.0)
    wins: int = Field(default=0)
    losses: int = Field(default=0)
    trades: int = Field(default=0)
    params_json: str = '{}'

    def save(self):
        with Session(engine) as session:
            session.add(self)
            session.commit()
            session.refresh(self)

    @property
    def days_since_created(self):
        return (datetime.now() - self.date).days

    def is_valid(self, min_avg_profit, min_trades):
        """
        Check if the backtest result is valid

        :param min_avg_profit: minimum average profit
        :param min_trades: minimum trades
        :return: True if valid, False otherwise
        """
        return self.ratio >= min_avg_profit and self.trades >= min_trades

    @property
    def valid_date(self):
        return self.days_since_created < Settings.max_days_since_created

    @classmethod
    def null(cls, parameters):
        return cls(
            pair=parameters.pair,
            strategy=parameters.strategy,
            days=parameters.days,
            ratio=0.0,
            wins=0,
            losses=0,
            trades=0,
            params_json='{}',
        )


class HyperoptResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pair: str
    strategy: str
    date: datetime = Field(default_factory=datetime.now)
    days: int
    ratio: float = Field(default=0.0)
    wins: int = Field(default=0)
    losses: int = Field(default=0)
    trades: int = Field(default=0)
    params_json: str = Field(default='{}')

    def save(self):
        with Session(engine) as session:
            session.add(self)
            session.commit()
            session.refresh(self)

    @property
    def days_since_created(self):
        return (datetime.now() - self.date).days

    def is_valid(self, min_avg_profit, min_trades):
        """
        Check if the backtest result is valid

        :param min_avg_profit: minimum average profit
        :param min_trades: minimum trades
        :return: True if valid, False otherwise
        """
        return self.ratio >= min_avg_profit and self.trades >= min_trades

    @property
    def valid_date(self):
        return self.days_since_created < Settings.max_days_since_created

    @property
    def params(self) -> dict:
        return rapidjson.loads(self.params_json)

    @classmethod
    def null(cls, parameters: HyperoptInput):
        return HyperoptResult(
            pair=parameters.pair,
            strategy=parameters.strategy,
            days=parameters.days,
            ratio=0.0,
            wins=0,
            losses=0,
            trades=0,
            params_json='{}',
        )


SQLModel.metadata.create_all(engine)
