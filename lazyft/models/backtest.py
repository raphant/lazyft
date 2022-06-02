from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import rapidjson
from freqtrade.commands import Arguments, start_plot_dataframe
from lazyft import paths
from lazyft.database import engine
from lazyft.loss_functions import (
    roi_and_profit_hyperopt_loss,
    sharpe_hyperopt_loss,
    sortino_daily,
    win_ratio_and_profit_ratio_loss,
)
from lazyft.models import PerformanceBase
from lazyft.models.base import ReportBase
from lazyft.models.hyperopt import HyperoptReport
from lazyft.util import calculate_win_ratio
from loguru import logger
from sqlmodel import Field, Relationship, Session, SQLModel


class BacktestPerformance(PerformanceBase):
    """
    A class model that represents the performance of a backtest.
    """

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
        return calculate_win_ratio(self.wins, self.losses, self.draws)

    @property
    def profit_percent(self):
        return self.profit_total_pct / 100

    def dict(self, *args, **kwargs):
        """
        It adds a new key to the dictionary.
        :return: A dictionary.
        """
        d = super().dict(
            *args,
            **kwargs,
        )
        d["profit_mean_pct"] = self.profit_ratio
        return d


class BacktestReport(ReportBase, table=True):
    """
    An SQLModel that stores the backtest run.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    hash: str
    session_id: Optional[str]
    ensemble: Optional[str]

    hyperopt_id: Optional[str] = Field(default=None, foreign_key="hyperoptreport.id")
    _hyperopt: Optional["HyperoptReport"] = Relationship()

    backtest_file_str: str = Field(default="")
    strategy_hash: str = Field(default="")
    exchange: str = Field(default="")

    # region Properties
    @property
    def strategy(self) -> str:
        """
        Get the strategy name
        :return: The strategy name
        :rtype: str
        """
        return list(self.load_data["strategy"].keys())[0]

    # @property
    # def exchange(self) -> str:
    #     """
    #     Get the exchange name
    #     """
    #     return self.backtest_data["exchange"]

    @property
    def load_data(self) -> dict:
        """
        Get the backtest data from the backtest_results directory

        :return: The backtest data
        :rtype: dict
        """

        return rapidjson.loads(
            Path(paths.BACKTEST_RESULTS_DIR, self.backtest_file_str).read_text()
        )

        # with Session(engine) as session:
        #     return rapidjson.loads(session.get(BacktestData, self.data_id).text)

    @property
    def backtest_data(self) -> dict:
        """
        This function is used to load the data for the backtest

        :return: A dictionary of the data for the strategy.
        :rtype: dict
        """
        strategy_ = self.load_data["strategy"][self.strategy]
        return strategy_

    @property
    def max_open_trades(self) -> int:
        """
        :return: Get the maximum number of open trades.
        :rtype: int
        """
        return self.backtest_data["max_open_trades"]

    @property
    def starting_balance(self) -> float:
        return float(self.backtest_data["starting_balance"])

    @property
    def stake_amount(self) -> float:
        return self.backtest_data["stake_amount"]

    @property
    def timeframe(self) -> str:
        return self.backtest_data["timeframe"]

    @property
    def drawdown(self) -> float:
        """
        :return: The max_drawdown_account
        :rtype: float
        """
        return self.backtest_data.get("max_drawdown_account", 0)

    @property
    def timerange(self) -> str:
        """
        :return: the timerange of the backtest in the format of YYYYMMDD-YYYYMMDD.
        :rtype: str
        """
        # format of start_date and end_date is YYYY-MM-DD HH:MM:SS
        # remove the time from the date and strip the '-'
        start_date: str = (
            self.backtest_data["backtest_start"].split(" ")[0].replace("-", "")
        )
        end_date: str = (
            self.backtest_data["backtest_end"].split(" ")[0].replace("-", "")
        )

        return f"{start_date}-{end_date}"

    @property
    def performance(self) -> BacktestPerformance:
        """
        :return: A summarized performance object of the backtest.
        :rtype: BacktestPerformance
        """
        totals = self.backtest_data["results_per_pair"].pop()
        totals.pop("key")
        totals["start_date"] = self.backtest_data["backtest_start"]
        totals["end_date"] = self.backtest_data["backtest_end"]
        totals["profit_total_pct"] = totals["profit_total_pct"] / 100
        totals["drawdown"] = self.drawdown
        totals["avg_duration"] = self.backtest_data["holding_avg"]
        return BacktestPerformance(**totals)

    @property
    def winning_pairs(self) -> pd.DataFrame:
        """
        The function takes in the trades dataframe and returns a dataframe with the following columns:

        * pair: The pair that was traded
        * profit_total: The total profit of the trades for this pair
        * profit_total_pct: The total profit of the trades for this pair as a percentage
        * profit_pct: The average profit of the trades for this pair as a percentage
        * count: The number of trades made for this pair

        :rtype: pd.DataFrame
        """
        trades = self.trades
        df: pd.DataFrame = trades.loc[trades.profit_ratio > 0]
        # df.set_index('pair', inplace=True)
        return (
            df.groupby(df["pair"])
            .aggregate(
                profit_total=pd.NamedAgg(column="profit_abs", aggfunc="sum"),
                profit_total_pct=pd.NamedAgg(column="profit_ratio", aggfunc="sum"),
                profit_pct=pd.NamedAgg(column="profit_ratio", aggfunc="mean"),
                count=pd.NamedAgg(column="pair", aggfunc="count"),
            )
            .sort_values("profit_total", ascending=False)
        )
        # return df.sort_values('profit_abs', ascending=False)

    @property
    def logs(self) -> str:
        """
        :return: The string representation of the log file.
        :rtype: str
        """
        if not self.log_file.exists():
            raise FileNotFoundError("Log file does not exist")
        return self.log_file.read_text()

    @property
    def log_file(self) -> Path:
        """
        :return: The path to the log file.
        :rtype: Path
        """
        return paths.BACKTEST_LOG_PATH.joinpath(str(self.id) + ".log")

    @property
    def df(self) -> pd.DataFrame:
        """
        :return: A dataframe summary of the backtest.
        :rtype: pd.DataFrame
        """
        df = super().df
        df.insert(2, "hyperopt_id", self.hyperopt_id)
        try:
            df.insert(
                13,
                "sortino",
                self.sortino_loss,
            )
        except Exception as e:
            logger.exception(e)

        return df

    @property
    def sortino_loss(self) -> float:
        return sortino_daily(
            results=self.trades,
            trade_count=self.performance.trades,
        )

    @property
    def sharpe_loss(self) -> float:
        return sharpe_hyperopt_loss(
            results=self.trades,
            trade_count=self.performance.trades,
            days=self.performance.days,
        )

    @property
    def roi_loss(self) -> float:
        """
        A custom loss function that is defined in `loss_functions.py`

        .. literalinclude:: ../lazyft/loss_functions.py
            :pyobject: roi_and_profit_hyperopt_loss
        :return: The calculated loss
        :rtype: float


        """
        return roi_and_profit_hyperopt_loss(
            results=self.trades,
            trade_count=self.performance.trades,
        )

    @property
    def win_ratio_loss(self) -> float:
        """
        .. literalinclude:: ../lazyft/loss_functions.py
            :pyobject: win_ratio_and_profit_ratio_loss
        """
        return win_ratio_and_profit_ratio_loss(
            results=self.trades,
            trade_count=self.performance.trades,
        )

    @property
    def trades(self) -> pd.DataFrame:
        df = pd.DataFrame(self.backtest_data["trades"])
        df.open_date = pd.to_datetime(df.open_date)
        df.close_date = pd.to_datetime(df.close_date)
        return df

    @property
    def pairlist(self) -> list[str]:
        return self.backtest_data["pairlist"]

    def as_df(self, key: str) -> pd.DataFrame:
        """Get a key from the backtest data as a DataFrame"""
        if key not in self.backtest_data:
            raise KeyError(
                "%s not found in backtest data. Available keys are: %s"
                % (key, ", ".join(self.backtest_data.keys()))
            )
        return pd.DataFrame(self.backtest_data[key])

    @property
    def pair_performance(self) -> pd.DataFrame:
        """
        :return: A dataframe with the performance of each pair.
        """
        return pd.DataFrame(self.backtest_data["results_per_pair"])

    @property
    def sell_reason_summary(self) -> pd.DataFrame:
        """
        :return: A dataframe with the sell reasons for each pair.
        """
        return pd.DataFrame(self.backtest_data["sell_reason_summary"])

    @property
    def hyperopt_report(self) -> HyperoptReport | None:
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
            self.strategy,
            self.id,
            self.backtest_data,
            self.backtest_data["stake_currency"],
            hyperopt_id=self.hyperopt_id,
        )

    # endregion

    def trades_to_csv(self, name=""):
        """
        The function trades_to_csv() takes a backtest object and exports the trades to a csv file

        :param name: The name of the strategy
        :return: A CSV file with the trades for the backtest.
        """
        path = paths.BASE_DIR.joinpath("exports/")
        path.mkdir(exist_ok=True)
        if not name:
            name = (
                f"{self.strategy}-"
                f"${self.starting_balance}-"
                f"{(self.performance.end_date - self.performance.start_date).days}_days"
            )
            if self.id:
                name += f"-{self.id}"
            name += ".csv"

        df_trades = self.trades
        df_trades.open_date = df_trades.open_date.apply(lambda d: d.strftime("%x %X"))
        df_trades.close_date = df_trades.close_date.apply(lambda d: d.strftime("%x %X"))
        csv = df_trades.to_csv(path.joinpath(name), index=False)
        logger.info(
            f"Exported trades for backtest #{self.id} to -> {path.joinpath(name)}"
        )
        return csv

    def delete(self, session: Session):
        """
        Delete the data from the database and delete the log file

        :param session: The session object that is used to connect to the database
        :type session: Session
        """
        # data = session.get(BacktestData, self.data_id)
        # session.delete(data)
        # self.log_file.unlink(missing_ok=True)

    def plot(self):
        """
        Plot the backtest results

        :return:
        """
        import plotly.express as px
        from lazyft.plot import calculate_equity, get_dates_from_strategy

        strategy_stats = self.backtest_data
        df = pd.DataFrame({"date": get_dates_from_strategy(strategy_stats)})
        df.loc[:, f"equity_daily"] = calculate_equity(strategy_stats)
        cols = [col for col in df.columns if "equity_daily" in col]
        fig = px.line(
            df,
            x="date",
            y=cols,
            title=f"Equity Curve {self.strategy}-{self.hyperopt_id or 'NO_ID'} | "
            f"Interval={self.timeframe} Timerange={self.timerange}, "
            f"Total profit=${self.performance.profit_total_abs:.2f}, "
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
        """
        It plots the monthly profit of the strategy.
        """
        import plotly.express as px

        trades_df = self.trades
        trades_df = trades_df.resample("M", on="close_date").sum()
        trades_df["profit_abs"] = trades_df["profit_abs"].round(2)
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
        """
        It plots the weekly profit of the strategy.
        """
        import plotly.express as px

        trades_df = self.trades
        trades_df = trades_df.resample("W", on="close_date").sum()
        trades_df["profit_abs"] = trades_df["profit_abs"].round(2)
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

    def plot_daily(self):
        """
        It plots the daily profit of the strategy.
        """
        import plotly.express as px

        trades_df = self.trades
        trades_df = trades_df.resample("D", on="close_date").sum()
        trades_df["profit_abs"] = trades_df["profit_abs"].round(2)
        fig = px.line(
            trades_df,
            # x="index",
            y="profit_abs",
            text="profit_abs",
            title=f"Daily Profit {self.strategy} | Interval={self.timeframe} Timerange={self.timerange}, "
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

    def store_trades_plot(self, *pair: str, config_file: Path | str):
        """
        It creates a temporary file, writes the backtest data to it, and then runs the plot-dataframe
        cli command with the temporary file as the input

        :param : `strategy`: The strategy to use
        :type : str
        :param config_file: The path to the configuration file
        :type config_file: Union[Path | str]
        """
        # create temp file
        import tempfile

        tmp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        # write backtest data to temp file
        path = Path(tmp_file.name)
        path.write_text(rapidjson.dumps(self.load_data))
        cli_args = (
            f"plot-dataframe --strategy {self.strategy} "
            f"--export-filename {path} "
            f'-p {" ".join(pair)} -c {config_file}'
        )
        logger.info(f"Running plot-dataframe with args: {cli_args}")
        args = Arguments(cli_args.split()).get_parsed_arg()
        start_plot_dataframe(args)
        tmp_file.close()


SQLModel.metadata.create_all(engine)
