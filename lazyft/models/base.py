from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any, Optional, Union, TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session

from lazyft.database import engine

if TYPE_CHECKING:
    from lazyft.models.backtest import BacktestPerformance
    from lazyft.models.hyperopt import HyperoptPerformance


class PerformanceBase(BaseModel):
    start_date: datetime
    end_date: datetime
    trades: int
    wins: int
    losses: int
    draws: int
    drawdown: float
    avg_duration: Any

    @property
    @abstractmethod
    def profit(self) -> float:
        ...

    @property
    @abstractmethod
    def profit_ratio(self) -> float:
        ...

    @property
    def score(self):
        """
        The score function returns the profit ratio times the number of trades divided by the number of
        days multiplied by 100
        :return: The score of the strategy
        """
        return (self.profit_ratio * self.trades) / self.days * 100

    @property
    def days(self):
        """
        Return the number of days between the start and end dates
        """
        return max((self.end_date - self.start_date).days, 1)

    # noinspection PyUnresolvedReferences
    @property
    def ppd(self):
        """Profit per day"""
        ppd = self.profit_percent / (self.end_date - self.start_date).days
        return round(ppd, 2)

    @property
    def tpd(self):
        """Trades per day"""
        tpd = self.trades / (self.end_date - self.start_date).days
        return round(tpd, 1)

    @property
    def df(self):
        """
        This function returns a pandas dataframe of the dictionary of the class
        :return: A single row of a dataframe
        """
        return pd.DataFrame([self.dict()])

    @property
    def win_loss_ratio(self):
        """
        Return the ratio of wins to losses
        :return: The win/loss ratio.
        """
        return (self.wins + self.draws) / max(self.wins + self.draws + self.losses, 1)


class ReportBase(SQLModel):
    id: Optional[int]
    date: datetime = Field(default_factory=datetime.now)
    tag: str = ""

    @property
    @abstractmethod
    def performance(self) -> 'Union[HyperoptPerformance, BacktestPerformance]':
        ...

    # noinspection PyUnresolvedReferences
    @property
    def df(self):
        """
        A DataFrame representation of the report

        :return: A DataFrame
        :rtype: pd.DataFrame
        """
        try:
            n_pairlist = len(self.pairlist.split(","))
        except AttributeError:
            n_pairlist = len(self.pairlist)
        d = dict(
            id=self.id,
            strategy=self.strategy,
            date=self.date,
            exchange=self.exchange,
            m_o_t=self.max_open_trades,
            stake=self.stake_amount,
            balance=self.starting_balance,
            n_pairlist=n_pairlist,
            # ppd=self.performance.ppd,
            # tpd=self.performance.tpd,
            avg_profit_pct=self.performance.profit_ratio,
            avg_duration=self.performance.avg_duration,
            wins=self.performance.wins,
            losses=self.performance.losses,
            # score=self.performance.score,
            drawdown=self.performance.drawdown,
            total_profit_pct=self.performance.profit_total_pct,
            total_profit=self.performance.profit,
            trades=self.performance.trades,
            days=self.performance.days,
            tag=self.tag,
        )
        df = pd.DataFrame([d])
        df.total_profit = df.total_profit.apply(lambda v: round(v, 2))
        df.date = df.date.apply(lambda date: date.strftime("%x %X"))
        df.balance = df.balance.astype(int)
        return df

    def save(self):
        """
        Save the current state of the object to the database


        :return: The saved report.
        :rtype: ReportBase
        """
        with Session(engine) as session:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self
