import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import rapidjson
from dateutil import parser
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass

from lazyft import logger, paths


class Report(BaseModel):
    report_id: str = Field(default_factory=uuid.uuid4)
    param_id: str = Field(default_factory=uuid.uuid4)
    # id: str
    strategy: str
    exchange: str
    balance_info: Optional[dict]
    date: datetime = Field(default_factory=datetime.now)
    pairlist: list[str] = []
    tag: str = ''

    @property
    def id(self):
        return self.param_id

    class Config:
        allow_population_by_field_name = True


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

    @property
    def df(self):
        return pd.DataFrame([self.dict()])


class BacktestReport(Report):
    performance: BacktestPerformance
    json_file: Path
    hash: str
    session_id: Optional[str]

    @property
    def trades(self):
        df = pd.DataFrame(self.backtest_data['strategy'][self.strategy]['trades'])
        df.open_date = pd.to_datetime(df.open_date)
        df.close_date = pd.to_datetime(df.open_date)
        return df

    @property
    def pair_performance(self):
        return pd.DataFrame(
            self.backtest_data['strategy'][self.strategy]['results_per_pair']
        )

    @property
    def backtest_data(self):
        return rapidjson.loads(self.json_file.read_text())

    def trades_to_csv(self, name=''):
        path = paths.BASE_DIR.joinpath('exports/')
        path.mkdir(exist_ok=True)
        if not name:
            name = (
                f'{self.strategy}-'
                f'${self.balance_info["starting_balance"]}-'
                f'{(self.performance.end_date - self.performance.start_date).days}_days'
            )
            if self.id:
                name += f'-{self.id}'
            name += '.csv'

        df_trades = self.trades
        df_trades.open_date = df_trades.open_date.apply(lambda d: d.strftime('%x %X'))
        df_trades.close_date = df_trades.close_date.apply(lambda d: d.strftime('%x %X'))
        csv = df_trades.to_csv(path.joinpath(name), index=False)
        logger.info('Created {}', path.joinpath(name))
        return csv


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

    @property
    def df(self):
        return pd.DataFrame([self.dict()])


class HyperoptReport(Report):
    performance: HyperoptPerformance
    params_file: Path
    hyperopt_file: Path = ''

    def parameters(self):
        return rapidjson.loads(self.params_file.read_text())


class HyperoptRepo(BaseModel):
    reports: list[HyperoptReport] = []


class RemotePreset(BaseModel):
    address: str
    path: str
    port: int = 22

    @property
    def opt_port(self):
        if self.port != 22:
            return ['-e', f'ssh -p {self.port}']
        return ['']


@dataclass
class Environment:
    data: dict
    file: Path


@dataclass
class RemoteBotInfo:
    bot_id: int
    _env_file = None

    @property
    def strategy(self) -> str:
        return self.env.data['STRATEGY']


@dataclass
class Strategy:
    name: str = None
    id: str = None

    def __post_init__(self):
        if not self.name:
            assert self.id, 'Need a strategy name or ID'
            from lazyft.strategy import StrategyTools

            self.name = StrategyTools.get_name_from_id(self.id)

    def as_pair(self):
        return self.name, self.id
