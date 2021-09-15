import uuid
from abc import abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import rapidjson
from freqtrade.optimize.hyperopt_loss_sharpe import SharpeHyperOptLoss
from freqtrade.optimize.hyperopt_loss_sortino import (
    SortinoHyperOptLoss,
)
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass

from lazyft import logger, paths
from lazyft.loss_functions.ROIAndProfitHyperOptLoss import ROIAndProfitHyperOptLoss
from lazyft.loss_functions.WinRatioAndProfitRatioLoss import WinRatioAndProfitRatioLoss


class Performance(BaseModel):
    start_date: datetime
    end_date: datetime
    trades: int

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
        return ((self.profit_ratio / 100) * self.trades) / self.days * 100

    @property
    def days(self):
        return (self.end_date - self.start_date).days

    @property
    def ppd(self):
        """Profit per day"""
        ppd = self.profit / (self.end_date - self.start_date).days
        return round(ppd, 2)

    @property
    def tpd(self):
        """Trades per day"""
        tpd = self.trades / (self.end_date - self.start_date).days
        return round(tpd, 1)

    @property
    def df(self):
        return pd.DataFrame([self.dict()])


class HyperoptPerformance(Performance):
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

    @property
    def total_profit_pct(self):
        return self.profit_percent

    @property
    def profit_ratio(self) -> float:
        return self.avg_profits

    @property
    def profit(self):
        return self.tot_profit


class BacktestPerformance(Performance):
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

    @property
    def profit_ratio(self) -> float:
        return self.avg_profit_pct * 100

    @property
    def profit(self):
        return self.total_profit_market


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
    performance: 'Union[HyperoptPerformance, BacktestPerformance]'

    @property
    def id(self):
        return self.param_id

    class Config:
        allow_population_by_field_name = True

    @property
    def df(self):
        d = dict(
            strategy=self.strategy,
            date=self.date,
            hyperopt_id=self.id,
            exchange=self.exchange,
            m_o_t=self.balance_info['max_open_trades'],
            stake=self.balance_info['stake_amount'],
            balance=self.balance_info['starting_balance'],
            # ppd=self.performance.ppd,
            # tpd=self.performance.tpd,
            score=self.performance.score,
            avg_profit_pct=self.performance.profit_ratio,
            total_profit_pct=self.performance.total_profit_pct,
            total_profit=self.performance.profit,
            trades=self.performance.trades,
            days=self.performance.days,
            tag=self.tag,
        )
        df = pd.DataFrame([d])
        df.total_profit = df.total_profit.apply(lambda v: round(v, 2))
        df.date = df.date.apply(lambda date: date.strftime('%x %X'))
        df.balance = df.balance.astype(int)
        return df


class BacktestReport(Report):
    performance: BacktestPerformance
    json_file: Path
    hash: str
    session_id: Optional[str]

    @property
    def df(self):
        df = super().df
        df.insert(
            10,
            'roiloss',
            self.roi_loss,
        )
        df.insert(
            11,
            'sortino',
            self.sortino_loss,
        )
        df.insert(
            11,
            'winratioloss',
            self.win_ratio_loss,
        )
        df.insert(
            12,
            'sharpe_loss',
            self.sharp_loss,
        )

        return df

    @property
    def sortino_loss(self):
        return SortinoHyperOptLoss.hyperopt_loss_function(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

    @property
    def sharp_loss(self):
        return SharpeHyperOptLoss.hyperopt_loss_function(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

    @property
    def roi_loss(self):
        return ROIAndProfitHyperOptLoss.hyperopt_loss_function(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

    @property
    def win_ratio_loss(self):
        return WinRatioAndProfitRatioLoss.hyperopt_loss_function(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

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

    def delete(self):
        self.json_file.unlink(missing_ok=True)


class HyperoptReport(Report):
    performance: HyperoptPerformance
    params_file: Path
    hyperopt_file: Path = ''

    def parameters(self):
        return rapidjson.loads(self.params_file.read_text())

    def delete(self):
        self.hyperopt_file.unlink(missing_ok=True)
        self.params_file.unlink(missing_ok=True)


class BacktestRepo(BaseModel):
    reports: list[BacktestReport] = []


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
