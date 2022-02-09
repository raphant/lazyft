from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import rapidjson
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, create_engine, Session

from lazyft.paths import BASE_DIR
from lft_rest import Settings

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
    timeframe_detail: str


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
    profit_per_trade: float = Field(default=0.0)
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
    def win_ratio(self):
        return (self.wins / self.trades) if self.trades else 0.0

    @property
    def days_since_created(self):
        return (datetime.now() - self.date).days

    def is_valid(self, min_avg_profit, min_trades, min_win_ratio):
        """
        Check if the backtest result is valid

        :param min_avg_profit: minimum average profit
        :param min_trades: minimum trades
        :param min_win_ratio: minimum win ratio
        :return: True if valid, False otherwise
        """
        return (
            self.profit_per_trade >= min_avg_profit
            and self.trades >= min_trades
            and self.wins / self.trades >= min_win_ratio
        )

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
    profit_per_trade: float = Field(default=0.0)
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

    def is_valid(self, min_avg_profit, min_trades, min_win_ratio):
        """
        Check if the backtest result is valid

        :param min_avg_profit: minimum average profit
        :param min_trades: minimum trades
        :param min_win_ratio: minimum win ratio
        :return: True if valid, False otherwise
        """
        return (
            self.profit_per_trade >= min_avg_profit
            and self.trades >= min_trades
            and self.win_ratio >= min_win_ratio
        )

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
            profit_per_trade=0.0,
            wins=0,
            losses=0,
            trades=0,
            params_json='{}',
        )

    @property
    def win_ratio(self):
        return (self.wins / self.trades) if self.trades else 0.0


SQLModel.metadata.create_all(engine)


def save_all_hyperopt_results(output_name='hyperopt_results.json'):
    """
    Load all hyperopt results from the database and save them as json files
    :return:
    """

    class HyperoptRepo(BaseModel):
        results: list[HyperoptResult]

    with Session(engine) as session:
        results = session.query(HyperoptResult).all()
        repo = HyperoptRepo(results=results)
        with open(output_name, 'w') as f:
            f.write(repo.json())
    print(f'Saved {len(results)} results to {output_name}')


def save_all_backtest_results(output_name='backtest_results.json'):
    """
    Load all backtest results from the database and save them as json files
    :return:
    """

    class BacktestRepo(BaseModel):
        results: list[BacktestResult]

    with Session(engine) as session:
        results = session.query(BacktestResult).all()
        repo = BacktestRepo(results=results)
        with open(output_name, 'w') as f:
            f.write(repo.json())
    print(f'Saved {len(results)} results to {output_name}')


def load_all_hyperopt_results(input_name='hyperopt_results.json'):
    """
    Load all hyperopt results from the json file and rename the 'ratio' column to 'profit_per_trade'
    :param input_name:
    :return:
    """
    with open(input_name, 'r') as f:
        repo = rapidjson.loads(f.read())
    results = repo['results']
    for result in results:
        result['profit_per_trade'] = result['ratio']
        del result['ratio']
    with Session(engine) as session:
        for result in results:
            session.add(HyperoptResult(**result))
        session.commit()
    print(f'Loaded {len(results)} results from {input_name}')


def load_all_backtest_results(input_name='backtest_results.json'):
    """
    Load all backtest results from the json file and rename the 'ratio' column to 'profit_per_trade'
    :param input_name:
    :return:
    """
    with open(input_name, 'r') as f:
        repo = rapidjson.loads(f.read())
    results = repo['results']
    for result in results:
        result['profit_per_trade'] = result['ratio']
        del result['ratio']
    with Session(engine) as session:
        for result in results:
            session.add(BacktestResult(**result))
        session.commit()
    print(f'Loaded {len(results)} results from {input_name}')
