from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field


class BalanceInfo(BaseModel):
    starting_balance: float
    stake_amount: Union[str, float]
    max_open_trades: int


class Report(BaseModel):
    id: str
    strategy: str
    exchange: str
    balance_info: Optional[BalanceInfo] = None
    date: datetime = Field(default_factory=datetime.now)
    pairlist: list[str] = []
    tags: list[str] = []


class BacktestPerformance(BaseModel):
    trades: int
    avg_profit_pct: float
    accumulative_profit: float
    profit_sum: float
    profit_sum_pct: float
    total_profit_market: float
    total_profit_pct: float
    profit_total_pct: float
    duration_avg: timedelta
    wins: int
    draws: int
    losses: int
    start_date: datetime
    end_date: datetime

    @property
    def profit(self):
        return self.total_profit_market


class BacktestReport(Report):
    performance: BacktestPerformance
    json_file: Path
    hash: str


class BacktestRepo(BaseModel):
    reports: list[BacktestReport] = []


class HyperoptPerformance(BaseModel):
    trades: int
    wins: int
    losses: int
    draws: int
    avg_profits: float
    med_profit: float
    tot_profit: float
    profit_percent: float
    avg_duration: str
    loss: float
    seed: int
    start_date: datetime
    end_date: datetime

    @property
    def profit(self):
        return self.tot_profit


class HyperoptReport(Report):
    performance: HyperoptPerformance
    params_file: str


class HyperoptRepo(BaseModel):
    reports: list[HyperoptReport] = []
