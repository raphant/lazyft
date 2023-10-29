from __future__ import annotations

import sqlite3
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Optional

import pandas as pd
import rapidjson
from _operator import itemgetter
from diskcache import Index
from freqtrade.misc import deep_merge_dicts
from freqtrade.optimize import optimize_reports
from freqtrade.optimize.hyperopt_tools import HyperoptTools
from loguru import logger
from sqlmodel import Field, SQLModel

from lazyft import paths, util
from lazyft.database import engine
from lazyft.models import PerformanceBase, ReportBase
from lazyft.strategy import get_file_name
from lazyft.util import calculate_win_ratio, get_last_hyperopt_file_name, remove_cache


def create_cache() -> tuple[Index, Index]:
    """
    Create the cache for the performance table

    :return: A cache and a temporary cache
    :rtype: tuple[diskcache.Index, diskcache.Index]
    """
    try:
        cache = Index(str(paths.CACHE_DIR / "models"))
    except sqlite3.DatabaseError:  # Database is malformed
        # remove cache/models with shutil.rmtree
        logger.info("Cache database is malformed, removing cache/models")
        remove_cache(paths.CACHE_DIR / "models")
        cache = Index(str(paths.CACHE_DIR / "models"))
    return cache, Index(tempfile.gettempdir())


cache, tmp_cache = create_cache()


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

    @property
    def win_ratio(self):
        """
        Returns the win ratio of the backtest. Takes draws into account.
        :return: win ratio
        """
        return calculate_win_ratio(self.wins, self.losses, self.draws)


class HyperoptReport(ReportBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="The id of the report")
    epoch: int
    hyperopt_file_str: str = Field(default="", description="The hyperopt file name")
    strategy_hash: str = Field(default="", description="The strategy hash used for integrity")
    exchange: str = Field(default="", description="The exchange used for the backtest")

    # region properties
    @property
    def filtered_results(self) -> tuple[list, int]:
        """
        Return filtered results.

        :return: A tuple of the filtered results and the number of results.
        :rtype: tuple[list, int]
        """
        config = {"user_data_dir": paths.USER_DATA_DIR}
        return HyperoptTools.load_filtered_results(self.hyperopt_file, config)

    @property
    def result_dict(self) -> dict:
        """
        Returns a dictionary with the results of the hyperopt run.
        Will cache the result for faster access.
        If the report is not saved to the database, the report will be temporarily cached.

        :raises IndexError: If the hyperopt does not exist.
        :return: A dictionary with the results of the hyperopt run.
        :rtype: dict
        """
        _cache = cache if self.id else tmp_cache
        try:
            if (self.hyperopt_file_str, self.epoch) in _cache:
                return _cache[self.hyperopt_file_str, self.epoch]
        except sqlite3.DatabaseError:
            remove_cache(_cache.directory)
            return self.result_dict
        logger.info("Loading and caching hyperopt results for id {}...", self.id)
        try:
            data = self.all_epochs[self.epoch]
        except IndexError:
            logger.error("Epoch {} not found in hyperopt results for {}", self.epoch, self.id)
            logger.info("Available epochs: {}", self.total_epochs)
            raise IndexError(
                f"Epoch {self.epoch} not found in hyperopt results for {self.id}. Available epochs: {self.total_epochs}"
            )
        _cache[self.hyperopt_file_str, self.epoch] = data
        return data

    @property
    def all_epochs(self) -> list[dict]:
        """
        Returns a list of all epochs of the hyperopt run.

        :return: A list of all epochs of the hyperopt run.
        :rtype: list[dict]
        """
        return self.filtered_results[0]

    @property
    def total_epochs(self) -> int:
        """
        :return: The total number of epochs of the hyperopt run.
        :rtype: int
        """
        return self.filtered_results[1]

    @property
    def backtest_data(self) -> dict:
        """
        :return: The backtest data of the best hyperopt run.
        :rtype: dict
        """
        return self.result_dict["results_metrics"]

    @property
    def strategy(self) -> str:
        """
        :return: The name of the strategy used for the hyperopt run.
        :rtype: str
        """
        return self.backtest_data["strategy_name"]

    @property
    def hyperopt_file(self) -> Path:
        """
        :return: The path to the hyperopt file.

        :return: A path to the hyperopt file.
        :rtype: Path
        """
        return paths.HYPEROPT_RESULTS_DIR / Path(self.hyperopt_file_str).name

    @property
    def performance(self) -> HyperoptPerformance:
        """
        :return: The performance of the best hyperopt run.

        :return: A HyperoptPerformance object.
        :rtype: HyperoptPerformance
        """
        return HyperoptPerformance(
            wins=self.backtest_data["wins"],
            losses=self.backtest_data["losses"],
            draws=self.backtest_data["draws"],
            avg_profits=self.backtest_data["profit_mean"],
            med_profit=self.backtest_data["profit_median"],
            profit_percent=self.backtest_data["profit_total"],
            tot_profit=self.backtest_data["profit_total_abs"],
            avg_duration=self.backtest_data["holding_avg"],
            start_date=self.backtest_data["backtest_start"],
            end_date=self.backtest_data["backtest_end"],
            seed=-1,
            trades=self.backtest_data["total_trades"],
            loss=self.loss,
            drawdown=self.drawdown,
        )

    @property
    def stake_currency(self) -> str:
        """
        :return: The stake currency.
        :rtype: str
        """
        return self.backtest_data["stake_currency"]

    @property
    def stake_amount(self) -> float:
        """
        :return: The stake amount.
        :rtype: float
        """
        return self.backtest_data["stake_amount"]

    @property
    def starting_balance(self) -> float:
        """
        :return: The starting balance.
        :rtype: float
        """
        return self.backtest_data["starting_balance"]

    @property
    def max_open_trades(self) -> int:
        """
        :return: The maximum number of open trades.
        :rtype: int
        """
        return self.backtest_data["max_open_trades"]

    @property
    def timeframe(self) -> str:
        """
        :return: The timeframe.
        :rtype: str
        """
        return self.backtest_data["timeframe"]

    @property
    def timerange(self) -> str:
        """
        :return: The timerange.
        :rtype: str
        """
        return self.backtest_data["timerange"]

    @property
    def pairlist(self) -> list[str]:
        """
        :return: The pairlist.
        :rtype: list[str]
        """
        return self.backtest_data["pairlist"]

    @property
    def log_file(self) -> Path | None:
        """
        :return: The log file.
        :rtype: Path | None
        """
        try:
            return paths.HYPEROPT_LOG_PATH.joinpath(str(self.id) + ".log")
        except FileNotFoundError:
            logger.warning("Log file not found for {}", self.id)

    @property
    def loss(self) -> float:
        """
        :return: The loss of the best hyperopt run.
        :rtype: float
        """
        return self.result_dict["loss"]

    @property
    def parameters(self) -> dict:
        """
        :return: The final parameters of the hyperopt.
        :rtype: dict
        """
        final_params = deepcopy(self.result_dict["params_not_optimized"])
        final_params = deep_merge_dicts(self.result_dict["params_details"], final_params)
        date = self.date.strftime("%x %X")
        final_params = {
            "strategy_name": self.strategy,
            "params": final_params,
            "ft_stratparam_v": 1,
            "export_time": date,
        }
        return final_params

    @property
    def parameters_path(self) -> Path:
        """
        :return: A path to the parameters file.
        :rtype: Path
        """
        file_name = get_file_name(self.strategy)
        return paths.STRATEGY_DIR.joinpath(file_name.replace(".py", "") + ".json")

    @property
    def drawdown(self) -> float:
        """
        :return: The drawdown of the best hyperopt run.
        :rtype: float
        """
        return self.backtest_data["max_drawdown_account"]

    @property
    def report_text(self) -> str:
        """
        :return: The backtest summary of the best hyperopt run.
        :rtype: str
        """
        from lazyft.reports import backtest_results_as_text

        return backtest_results_as_text(
            self.strategy,
            self.id,
            self.backtest_data,
            self.backtest_data["stake_currency"],
            hyperopt=True,
        )

    # endregion

    def export_parameters(self, path: Path = None) -> None:
        """
        Export the parameters of the hyperopt run to a json file.

        :param path: Optional path to export the parameters to.
        :type path: Path
        :return: None
        """

        path = path or self.parameters_path
        Path(path).write_text(rapidjson.dumps(self.parameters))
        logger.info("Exported parameters for report {} to {}", self.id, path)

    def delete(self, *args) -> None:
        """
        Delete the hyperopt run.
        """
        # self.hyperopt_file.unlink(missing_ok=True)
        self.log_file.unlink(missing_ok=True)

    def hyperopt_list_to_df(self) -> pd.DataFrame:
        """
        Convert the hyperopt list into a dataframe of performances.

        :return: A dataframe with the hyperopt list.
        :rtype: pd.DataFrame
        """
        trials = pd.json_normalize(self.all_epochs, max_level=1)
        trials = HyperoptTools.prepare_trials_columns(
            trials,
            "results_metrics.max_drawdown_abs" in trials.columns
            or "results_metrics.max_drawdown_account" in trials.columns,
        )
        trials.drop(
            columns=["is_initial_point", "is_best", "Best"],
            inplace=True,
            errors="ignore",
        )
        trials.set_index("Epoch", inplace=True)
        # "Avg duration" is a column with values the format of HH:MM:SS.
        # We want to turn this into hours
        avg_duration_hours = trials["Avg duration"].apply(
            lambda s: util.duration_string_to_timedelta(s).total_seconds() / 3600,
        )
        # insert avg_duration_seconds in the seventh position
        trials.insert(6, "Avg duration hours", avg_duration_hours)
        # strip each column name
        trials.columns = [c.strip() for c in trials.columns]
        return trials

    def show_epoch(self, epoch: int = None) -> None:
        """
        Show the hyperopt results for a specific epoch. If no epoch is specified,
        show the hyperopt results for the best epoch.

        :param epoch: The epoch number to show. If None, the best epoch will be shown
        :type epoch: int
        """
        if epoch:
            result = self.all_epochs[epoch - 1]
        else:
            result = self.result_dict
        optimize_reports.show_backtest_result(
            self.strategy,
            result["results_metrics"],
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
        """
        Create a new report from the hyperopt results for a specific epoch.

        :param epoch: The epoch number to create the report from.
        :return: The new report.
        """
        return HyperoptReport(
            epoch=epoch - 1,
            hyperopt_file_str=str(self.hyperopt_file),
            exchange=self.exchange,
            tag=self.tag,
            strategy_hash=self.strategy_hash,
        )

    def get_best_epoch(self):
        """
        Get the epoch number of the best epoch.

        :return: The epoch number of the best epoch.
        """
        sorted_epochs = sorted(self.all_epochs, key=itemgetter("loss"))
        return self.all_epochs.index(sorted_epochs[0])

    @classmethod
    def from_last_result(cls, epoch=0, exchange="kucoin"):
        """
        Return a HyperoptReport object from the last result of a hyperopt run.
        """
        return HyperoptReport(
            epoch=epoch,
            hyperopt_file_str=paths.HYPEROPT_RESULTS_DIR / get_last_hyperopt_file_name(),
            exchange=exchange,
        )

    @classmethod
    def from_hyperopt_result(cls, result_path: Path, exchange: str):
        """
        Return a HyperoptReport object from a hyperopt result file.
        """
        return HyperoptReport(epoch=0, hyperopt_file_str=str(result_path), exchange=exchange)


SQLModel.metadata.create_all(engine)
