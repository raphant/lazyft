from __future__ import annotations

import tempfile
from abc import abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from operator import itemgetter
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import rapidjson
from diskcache import Index
from freqtrade.misc import deep_merge_dicts
from freqtrade.optimize import optimize_reports
from freqtrade.optimize.hyperopt_tools import HyperoptTools
from freqtrade.optimize.optimize_reports import show_backtest_result
from freqtrade.resolvers import StrategyResolver
from pandas import json_normalize
from pydantic import BaseModel
from rich.console import Console
from rich.syntax import Syntax
from sqlmodel import SQLModel, Session, Field, Relationship, select

from lazyft import logger, paths, util, strategy
from lazyft.database import engine
from lazyft.loss_functions import (
    win_ratio_and_profit_ratio_loss,
    roi_and_profit_hyperopt_loss,
    sharpe_hyperopt_loss,
    sortino_hyperopt_loss,
)
from lazyft.strategy import get_file_name, get_name_from_id
from lazyft.util import get_last_hyperopt_file_path

cache = Index(str(paths.BASE_DIR / "cache"))
tmp_cache = Index(tempfile.gettempdir())


class PerformanceBase(BaseModel):
    start_date: datetime
    end_date: datetime
    trades: int
    wins: int
    losses: int
    draws: int
    drawdown: float

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
        return max((self.end_date - self.start_date).days, 1)

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

    @property
    def win_loss_ratio(self):
        return (self.wins + self.draws) / (self.wins + self.draws + self.losses)


class HyperoptPerformance(PerformanceBase):
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
    def profit_total_pct(self):
        return self.profit_percent

    @property
    def profit_ratio(self) -> float:
        return self.avg_profits

    @property
    def profit(self):
        return self.tot_profit


class BacktestPerformance(PerformanceBase):
    profit_mean_pct: float
    profit_sum_pct: float
    profit_total_abs: float
    profit_total_pct: float
    duration_avg: timedelta
    wins: int
    draws: int
    losses: int

    @property
    def profit_ratio(self) -> float:
        return self.profit_mean_pct / 100

    @property
    def profit(self):
        return self.profit_total_abs

    @property
    def win_ratio(self):
        """
        Returns the win ratio of the backtest. Takes draws into account.
        :return: win ratio
        """
        return self.wins / (self.losses + self.wins + self.draws)

    @property
    def profit_percent(self):
        return self.profit_total_pct / 100


class ReportBase(SQLModel):
    exchange: str
    id: Optional[int]
    date: datetime = Field(default_factory=datetime.now)
    tag: str = ''

    class Config:
        allow_population_by_field_name = True

    @property
    @abstractmethod
    def performance(self) -> Union[HyperoptPerformance, BacktestPerformance]:
        ...

    # noinspection PyUnresolvedReferences
    @property
    def df(self):
        try:
            n_pairlist = len(self.pairlist.split(','))
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
            wins=self.performance.wins,
            losses=self.performance.losses,
            score=self.performance.score,
            total_profit_pct=self.performance.profit_total_pct,
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

    def save(self):
        with Session(engine) as session:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self


class BacktestData(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str

    @property
    def parsed(self) -> dict:
        return rapidjson.loads(self.text)['strategy']

    def __str__(self) -> str:
        return f'Backtest for ID: {self.id} - {self.parsed["strategy"]}'


class HyperoptReport(ReportBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    epoch: int
    hyperopt_file_str: str = Field(default='')
    strategy_hash: str = Field(default='')

    # region properties
    @property
    def filtered_results(self):
        config = {'user_data_dir': paths.USER_DATA_DIR}
        return HyperoptTools.load_filtered_results(self.hyperopt_file, config)

    @property
    def result_dict(self) -> dict:
        """
        Returns a dictionary with the results of the hyperopt run
        Will cache the result for future use. If the report is not saved to the database,
        the report will be temporarily cached.
        """
        _cache = cache if self.id else tmp_cache
        if (self.hyperopt_file_str, self.epoch) in _cache:
            return _cache[self.hyperopt_file_str, self.epoch]
        logger.info('Loading and caching hyperopt results for id {}...', self.id)
        try:
            data = self.all_epochs[self.epoch]
        except IndexError:
            logger.error('Epoch {} not found in hyperopt results for {}', self.epoch, self.id)
            logger.info('Available epochs: {}', self.total_epochs)
            raise
        _cache[self.hyperopt_file_str, self.epoch] = data
        return data

    @property
    def all_epochs(self) -> list[dict]:
        return self.filtered_results[0]

    @property
    def total_epochs(self):
        return self.filtered_results[1]

    @property
    def backtest_data(self):
        return self.result_dict['results_metrics']

    @property
    def strategy(self):
        return self.backtest_data['strategy_name']

    @property
    def hyperopt_file(self) -> Path:
        return Path(self.hyperopt_file_str)

    @property
    def performance(self) -> HyperoptPerformance:
        return HyperoptPerformance(
            wins=self.backtest_data['wins'],
            losses=self.backtest_data['losses'],
            draws=self.backtest_data['draws'],
            avg_profits=self.backtest_data['profit_mean'],
            med_profit=self.backtest_data['profit_median'],
            profit_percent=self.backtest_data['profit_total'],
            tot_profit=self.backtest_data['profit_total_abs'],
            avg_duration=self.backtest_data['holding_avg'],
            start_date=self.backtest_data['backtest_start'],
            end_date=self.backtest_data['backtest_end'],
            seed=-1,
            trades=self.backtest_data['total_trades'],
            loss=self.loss,
            drawdown=self.drawdown,
        )

    @property
    def stake_currency(self):
        return self.backtest_data['stake_currency']

    @property
    def stake_amount(self):
        return self.backtest_data['stake_amount']

    @property
    def starting_balance(self):
        return self.backtest_data['starting_balance']

    @property
    def max_open_trades(self):
        return self.backtest_data['max_open_trades']

    @property
    def timeframe(self):
        return self.backtest_data['timeframe']

    @property
    def timerange(self):
        return self.backtest_data['timerange']

    @property
    def pairlist(self):
        return self.backtest_data['pairlist']

    @property
    def log_file(self):
        try:
            return paths.HYPEROPT_LOG_PATH.joinpath(str(self.id) + '.log')
        except FileNotFoundError:
            logger.warning('Log file not found for {}', self.id)

    @property
    def loss(self):
        return self.result_dict['loss']

    @property
    def parameters(self) -> dict:
        final_params = deepcopy(self.result_dict['params_not_optimized'])
        final_params = deep_merge_dicts(self.result_dict['params_details'], final_params)
        date = self.date.strftime('%x %X')
        final_params = {
            'strategy_name': self.strategy,
            'params': final_params,
            'ft_stratparam_v': 1,
            'export_time': date,
        }
        return final_params

    @property
    def parameters_path(self) -> Path:
        file_name = get_file_name(self.strategy)
        return paths.STRATEGY_DIR.joinpath(file_name.replace(".py", "") + ".json")

    @property
    def drawdown(self):
        return self.backtest_data['max_drawdown_account']

    @property
    def report_text(self):
        from lazyft.reports import backtest_results_as_text

        return backtest_results_as_text(
            self.strategy, self.backtest_data, self.backtest_data['stake_currency'], hyperopt=True
        )

    # endregion

    def export_parameters(self, path: Path = None) -> None:
        """
        Export the parameters of the hyperopt run to a json file.
        :param path: Optional path to export the parameters to.
        :return:
        """
        path = path or self.parameters_path
        path.write_text(rapidjson.dumps(self.parameters))
        logger.info('Exported parameters for report {} to {}', self.id, path)

    def delete(self, *args):
        # self.hyperopt_file.unlink(missing_ok=True)
        self.log_file.unlink(missing_ok=True)

    def hyperopt_list_to_df(self) -> pd.DataFrame:
        trials = json_normalize(self.all_epochs, max_level=1)
        trials = HyperoptTools.prepare_trials_columns(
            trials,
            'results_metrics.max_drawdown_abs' in trials.columns
            or 'results_metrics.max_drawdown_account' in trials.columns,
        )
        trials.drop(
            columns=['is_initial_point', 'is_best', 'Best'],
            inplace=True,
            errors='ignore',
        )
        trials.set_index('Epoch', inplace=True)
        # "Avg duration" is a column with values the format of HH:MM:SS.
        # We want to turn this into hours
        avg_duration_hours = trials['Avg duration'].apply(
            lambda s: util.duration_string_to_timedelta(s).total_seconds() / 3600,
        )
        # insert avg_duration_seconds in the seventh position
        trials.insert(6, 'Avg duration hours', avg_duration_hours)
        # strip each column name
        trials.columns = [c.strip() for c in trials.columns]
        return trials

    def show_hyperopt(self, epoch: int = None):
        if epoch:
            result = self.all_epochs[epoch - 1]
        else:
            result = self.result_dict
        optimize_reports.show_backtest_result(
            self.strategy,
            result['results_metrics'],
            self.stake_currency,
            [],
        )
        HyperoptTools.show_epoch_details(
            result,
            self.total_epochs,
            False,
            True,
        )

    def new_report_from_epoch(self, epoch: int):
        return HyperoptReport(
            epoch=epoch - 1,
            hyperopt_file_str=str(self.hyperopt_file),
            exchange=self.exchange,
            tag=self.tag,
            strategy_hash=self.strategy_hash,
        )

    def get_best_epoch(self):
        sorted_epochs = sorted(self.all_epochs, key=itemgetter('loss'))
        return self.all_epochs.index(sorted_epochs[0])

    @classmethod
    def from_last_result(cls, epoch=0, exchange='kucoin'):
        """
        Return a HyperoptReport object from the last result of a hyperopt run.
        """
        return HyperoptReport(
            epoch=epoch, hyperopt_file_str=str(get_last_hyperopt_file_path()), exchange=exchange
        )

    @classmethod
    def from_hyperopt_result(cls, result_path: Path, exchange: str):
        """
        Return a HyperoptReport object from a hyperopt result file.
        """
        return HyperoptReport(epoch=0, hyperopt_file_str=str(result_path), exchange=exchange)


class BacktestReport(ReportBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hash: str
    session_id: Optional[str]
    ensemble: Optional[str]

    hyperopt_id: Optional[str] = Field(default=None, foreign_key="hyperoptreport.id")
    _hyperopt: Optional['HyperoptReport'] = Relationship()

    # performance_id: Optional[int] = Field(
    #     default=None, foreign_key="backtestperformance.id"
    # )
    # _performance: BacktestPerformance = Relationship()

    data_id: Optional[int] = Field(default=None, foreign_key="backtestdata.id")
    _backtest_data: BacktestData = Relationship()

    strategy_hash: str = Field(default='')

    # region Properties
    @property
    def strategy(self):
        return list(self.load_data['strategy'].keys())[0]

    @property
    def exchange(self):
        return self.backtest_data['exchange']

    @property
    def load_data(self):
        with Session(engine) as session:
            return rapidjson.loads(session.get(BacktestData, self.data_id).text)

    @property
    def backtest_data(self) -> dict:
        strategy_ = self.load_data['strategy'][self.strategy]
        return strategy_

    @property
    def max_open_trades(self):
        return self.backtest_data['max_open_trades']

    @property
    def starting_balance(self):
        return float(self.backtest_data['starting_balance'])

    @property
    def stake_amount(self):
        return self.backtest_data['stake_amount']

    @property
    def timeframe(self):
        return self.backtest_data['timeframe']

    @property
    def drawdown(self):
        return self.backtest_data.get('max_drawdown_account', 0)

    @property
    def timerange(self) -> str:
        """
        Return the timerange of the backtest in the format of YYYYMMDD-YYYYMMDD.
        :return:
        """
        # format of start_date and end_date is YYYY-MM-DD HH:MM:SS
        # remove the time from the date and strip the '-'
        start_date: str = self.backtest_data['backtest_start'].split(' ')[0].replace('-', '')
        end_date: str = self.backtest_data['backtest_end'].split(' ')[0].replace('-', '')

        return f'{start_date}-{end_date}'

    @property
    def performance(self) -> BacktestPerformance:
        totals = self.backtest_data['results_per_pair'].pop()
        totals.pop('key')
        totals['start_date'] = self.backtest_data['backtest_start']
        totals['end_date'] = self.backtest_data['backtest_end']
        totals['profit_total_pct'] = totals['profit_total_pct'] / 100
        totals['drawdown'] = self.drawdown
        return BacktestPerformance(**totals)

    @property
    def winning_pairs(self) -> pd.DataFrame:
        trades = self.trades
        df: pd.DataFrame = trades.loc[trades.profit_ratio > 0]
        # df.set_index('pair', inplace=True)
        return (
            df.groupby(df['pair'])
            .aggregate(
                profit_total=pd.NamedAgg(column='profit_abs', aggfunc='sum'),
                profit_total_pct=pd.NamedAgg(column='profit_ratio', aggfunc='sum'),
                profit_pct=pd.NamedAgg(column='profit_ratio', aggfunc='mean'),
                count=pd.NamedAgg(column='pair', aggfunc='count'),
            )
            .sort_values('profit_total', ascending=False)
        )
        # return df.sort_values('profit_abs', ascending=False)

    @property
    def logs(self) -> str:
        if not self.log_file.exists():
            raise FileNotFoundError('Log file does not exist')
        return self.log_file.read_text()

    @property
    def log_file(self) -> Path:
        return paths.BACKTEST_LOG_PATH.joinpath(str(self.id) + '.log')

    @property
    def df(self):
        df = super().df
        df.insert(2, 'hyperopt_id', self.hyperopt_id)
        try:
            ...
            # df.insert(
            #     10,
            #     'roiloss',
            #     self.roi_loss,
            # )
            # df.insert(
            #     11,
            #     'sortino',
            #     self.sortino_loss,
            # )
            # df.insert(
            #     11,
            #     'winratioloss',
            #     self.win_ratio_loss,
            # )
            # df.insert(
            #     12,
            #     'sharpe_loss',
            #     self.sharp_loss,
            # )
        except Exception as e:
            logger.exception(e)

        return df

    @property
    def sortino_loss(self):
        return sortino_hyperopt_loss(
            results=self.trades,
            trade_count=self.performance.trades,
            days=self.performance.days,
        )

    @property
    def sharp_loss(self):
        return sharpe_hyperopt_loss(
            results=self.trades,
            trade_count=self.performance.trades,
            days=self.performance.days,
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
    def sell_reason_summary(self):
        return pd.DataFrame(self.backtest_data['sell_reason_summary'])

    @property
    def hyperopt_report(self):
        """
        Return the hyperopt report used for this backtest using self.hyperopt_id.
        Returns none if no hyperopt_id is set.
        """
        from lazyft.reports import get_hyperopt_repo

        return get_hyperopt_repo().get(self.hyperopt_id) if self.hyperopt_id else None

    @property
    def hyperopt_parameters(self):
        """
        Return the hyperopt parameters used for this backtest
        """
        return self.hyperopt_report.parameters if self.hyperopt_report else None

    @property
    def report_text(self):
        from lazyft.reports import backtest_results_as_text

        return backtest_results_as_text(
            self.strategy, self.backtest_data, self.backtest_data['stake_currency']
        )

    # endregion

    def trades_to_csv(self, name=''):
        path = paths.BASE_DIR.joinpath('exports/')
        path.mkdir(exist_ok=True)
        if not name:
            name = (
                f'{self.strategy}-'
                f'${self.starting_balance}-'
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

    def delete(self, session: Session):
        data = session.get(BacktestData, self.data_id)
        session.delete(data)
        self.log_file.unlink()

    def plot(self):
        """
        Plot the backtest results

        :return:
        """
        from lazyft.plot import get_dates_from_strategy, calculate_equity
        import plotly.express as px

        strategy_stats = self.backtest_data
        df = pd.DataFrame({"date": get_dates_from_strategy(strategy_stats)})
        df.loc[:, f'equity_daily'] = calculate_equity(strategy_stats)
        cols = [col for col in df.columns if "equity_daily" in col]
        fig = px.line(
            df,
            x="date",
            y=cols,
            title=f"Equity Curve {self.strategy}-{self.hyperopt_id or 'NO_ID'} | "
            f"Interval={self.timeframe} Timerange={self.timerange}, "
            f"Total profit=${self.performance.profit_total_abs:.2f}, "
            # f"Final profit=${(self.performance.profit_total_abs + self.starting_balance):.2f}, "
            f"Total pct={self.performance.profit_total_pct * 100:.2f}%, "
            f"Mean pct={self.performance.profit_mean_pct:.2f}%, "
            f"Trades={self.performance.trades}, "
            f"Wins={self.performance.wins}, "
            f"Losses={self.performance.losses}, "
            f"Draws={self.performance.draws}, "
            f"Win ratio={self.performance.win_ratio * 100:.2f}%",
        )
        fig.show(showgrid=True)

    def plot_monthly(self):
        import plotly.express as px

        trades_df = self.trades
        trades_df = trades_df.resample('M', on='close_date').sum()
        trades_df['profit_abs'] = trades_df['profit_abs'].round(2)
        fig = px.line(
            trades_df,
            # x="index",
            y="profit_abs",
            text="profit_abs",
            title=f"Monthly Profit {self.strategy} | Interval={self.timeframe} Timerange={self.timerange}, "
            f"Total profit=${self.performance.profit_total_abs:.2f}, "
            f"Final profit=${self.performance.profit_total_abs + self.starting_balance:.2f}, "
            f"Total pct={self.performance.profit_total_pct:.2f}%, "
            f"Mean pct={self.performance.profit_mean_pct:.2f}%, "
            f"Trades={self.performance.trades}, "
            f"Wins={self.performance.wins}, "
            f"Losses={self.performance.losses}, "
            f"Draws={self.performance.draws}, "
            f"Win ratio={self.performance.win_ratio * 100:.2f}%",
        )
        fig.show(showgrid=True)

    def plot_weekly(self):
        import plotly.express as px

        trades_df = self.trades
        trades_df = trades_df.resample('W', on='close_date').sum()
        trades_df['profit_abs'] = trades_df['profit_abs'].round(2)
        fig = px.line(
            trades_df,
            # x="index",
            y="profit_abs",
            text="profit_abs",
            title=f"Weekly Profit {self.strategy} | Interval={self.timeframe} Timerange={self.timerange}, "
            f"Total profit=${self.performance.profit_total_abs:.2f}, "
            f"Total pct={self.performance.profit_total_pct:.2f}%, "
            f"Mean pct={self.performance.profit_mean_pct:.2f}%, "
            f"Trades={self.performance.trades}, "
            f"Wins={self.performance.wins}, "
            f"Losses={self.performance.losses}, "
            f"Draws={self.performance.draws}, "
            f"Win ratio={self.performance.win_ratio * 100:.2f}%",
        )
        fig.show(showgrid=True)


class StrategyBackup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=False)
    text: str = Field(index=False)
    hash: str = Field(index=True)
    date: datetime = Field(default_factory=datetime.now)

    def save(self):
        with Session(engine) as session:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self

    def export_to(self, path: Union[Path, str]) -> Path:
        """
        Export the strategy to a file or directory.

        :param path: A file or a directory
        :return: The path to the exported file
        """
        if isinstance(path, str):
            path = Path(path)
        if path.is_dir():
            path = path / strategy.get_file_name(self.name)
        path.write_text(self.text)
        return path

    def print(self):
        console = Console()
        console.print(Syntax(self.text, lexer_name='python'))

    @classmethod
    def load_hash(cls, hash):
        with Session(engine) as session:
            statement = select(cls).where(cls.hash == hash)
            return session.exec(statement).first()

    @classmethod
    def first(cls):
        with Session(engine) as session:
            statement = select(cls).order_by(cls.date)
            return session.exec(statement).first()


class BacktestRepo(BaseModel):
    reports: list[BacktestReport] = []


class HyperoptRepo(BaseModel):
    reports: list[HyperoptReport] = []


class StrategyBackupRepo(BaseModel):
    reports: list[StrategyBackup] = []


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

    def save(self, new_data: dict = None):
        data = new_data or self.data
        self.update_db_file_name()
        new_text = "\n".join([f"{k}={v}" for k, v in data.items()]) + "\n"
        self.file.write_text(new_text)

    def update_db_file_name(self):
        mode = self.data.get("FREQTRADE__DRY_RUN", True)
        dry_run = "dry_run" if mode else "live"
        strategy = self.data["STRATEGY"]
        id = self.data["ID"]
        db_file = f"tradesv3.{strategy}-{dry_run}-{id}".rstrip("-") + ".sqlite"
        self.data["DB_FILE"] = db_file


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
    id: int = None
    args: dict = None

    def __post_init__(self):
        if not self.name:
            assert self.id, 'Need a strategy name or ID'

            self.name = get_name_from_id(self.id)

    @property
    def as_ft_strategy(self):
        assert self.args, 'Need strategy args'
        return StrategyResolver.load_strategy(self.args)

    @property
    def as_pair(self):
        return self.name, str(self.id)

    @property
    def timeframe(self):
        return self.as_ft_strategy.timeframe

    def __str__(self) -> str:
        return '-'.join(self.as_pair).rstrip('-')


SQLModel.metadata.create_all(engine)
