import uuid
from abc import abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import rapidjson
import sh
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass

from lazyft import logger, paths
from lazyft.loss_functions import (
    win_ratio_and_profit_ratio_loss,
    roi_and_profit_hyperopt_loss,
    sharpe_hyperopt_loss,
    sortino_hyperopt_loss,
)


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
    ensemble: list[str] = []

    @property
    def logs(self) -> str:
        log_path = paths.BACKTEST_LOG_PATH.joinpath(self.report_id + '.log')
        if not log_path.exists():
            return ''
        return log_path.read_text()

    @property
    def log_file(self):
        return paths.BACKTEST_LOG_PATH(self.report_id + '.log')

    @property
    def df(self):
        df = super().df

        try:
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
        except Exception as e:
            logger.exception(e)

        return df

    @property
    def sortino_loss(self):

        return sortino_hyperopt_loss(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

    @property
    def sharp_loss(self):

        return sharpe_hyperopt_loss(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

    @property
    def roi_loss(self):

        return roi_and_profit_hyperopt_loss(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

    @property
    def win_ratio_loss(self):

        return win_ratio_and_profit_ratio_loss(
            results=self.trades,
            trade_count=self.performance.trades,
            min_date=self.performance.start_date,
            max_date=self.performance.end_date,
        )

    @property
    def trades(self):
        df = pd.DataFrame(self.backtest_data['trades'])
        df.open_date = pd.to_datetime(df.open_date)
        df.close_date = pd.to_datetime(df.close_date)
        return df

    @property
    def pairlist(self) -> list[str]:
        return self.backtest_data['pairlist']

    def as_df(self, key: str):
        """Get a key from the backtest data as a DataFrame"""
        if key not in self.backtest_data:
            raise KeyError(
                '%s not found in backtest data. Available keys are: %s'
                % (key, ', '.join(self.backtest_data.keys()))
            )
        return pd.DataFrame(self.backtest_data[key])

    @property
    def pair_performance(self):
        return pd.DataFrame(self.backtest_data['results_per_pair'])

    @property
    def backtest_data(self) -> dict:
        file = self.json_file
        # this is so that this data can be retrieved from any PC
        # it makes the backtest_data relative to the current user_data directory
        path_from_user_data = str(file).split('/user_data/')[1]
        file = paths.USER_DATA_DIR.joinpath(path_from_user_data).resolve()
        return rapidjson.loads(file.read_text())['strategy'][self.strategy]

    @property
    def sell_reason_summary(self):
        return pd.DataFrame(self.backtest_data['sell_reason_summary'])

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
        self.log_file.unlink(missing_ok=True)


class HyperoptReport(Report):
    performance: HyperoptPerformance
    params_file: Path
    hyperopt_file: Path = ''
    pairlist: list[str] = []

    @property
    def log_file(self):
        return paths.HYPEROPT_LOG_PATH(self.report_id + '.log')

    def parameters(self):
        return rapidjson.loads(self.params_file.read_text())

    def delete(self):
        self.hyperopt_file.unlink(missing_ok=True)
        self.params_file.unlink(missing_ok=True)
        self.log_file.unlink(missing_ok=True)

    def print_hyperopt_list(self):
        text = sh.freqtrade(
            'hyperopt-list',
            '--hyperopt-filename',
            str(self.hyperopt_file),
            '--userdir',
            str(paths.USER_DATA_DIR),
        )
        print(text)

    def show_hyperopt(self, index=None):
        args = [
            'hyperopt-show',
            '--hyperopt-filename',
            str(self.hyperopt_file),
            '--userdir',
            str(paths.USER_DATA_DIR),
        ]
        if not index:
            args.insert(1, '--best')
        else:
            args.insert(1, '-n')
            args.insert(2, str(index))
        text = sh.freqtrade(*args)
        print(text)


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

    @property
    def as_pair(self):
        return self.name, self.id

    def __str__(self) -> str:
        return '-'.join(self.as_pair)
