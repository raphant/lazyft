from __future__ import annotations

import time
from datetime import datetime, timedelta
from queue import Empty, Queue
from threading import Thread
from typing import Optional, Union

import alive_progress
import dateutil.parser
import pytz
import sh
from freqtrade.data.history import load_pair_history
from pydantic import BaseModel

from lazyft import logger, paths
from lazyft.command_parameters import BacktestParameters, HyperoptParameters
from lazyft.config import Config
from lazyft.paths import USER_DATA_DIR
from lazyft.strategy import load_informative_intervals_and_pairs_from_strategy

if not paths.PAIR_DATA_DIR.exists():
    paths.PAIR_DATA_DIR.mkdir(parents=True)
utc = pytz.UTC

exec_log = logger.bind(type="general")


class DownloadRecord(BaseModel):
    """
    The DownloadRecord class is a model that defines the data to be stored in the database
    """

    requested_start_date: datetime
    actual_start_date: datetime
    end_date: datetime

    @property
    def reached_first_candle(self):
        """
        Returns True if the last requested start date is the before or the same day as the actual
        start date.
        If this is True then the beginning of the pairs candle lifetime has been reached.
        """
        return self.requested_start_date < self.actual_start_date


class History(BaseModel):
    """
    A convenience class to for storing/retrieving the history of a pair.
    """

    history: dict[str, DownloadRecord] = {}


def load_history(exchange: str, interval: str) -> History:
    """
    Load the download history from the file.
    """
    history_file = paths.PAIR_DATA_DIR.joinpath(exchange, f"{interval}.json")
    if not history_file.exists():
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text("{}")
    try:
        return History.parse_file(history_file)
    except Exception as e:
        raise Exception(f"Failed to load history file {history_file}: {e}")


def save_record(pair: str, record: DownloadRecord, exchange: str, interval: str):
    """
    It takes a pair, a record, an exchange, and an interval, and saves the record to the history file

    :param pair: The pair to save the record for
    :type pair: str
    :param record: The DownloadRecord object that was created by the download function
    :type record: DownloadRecord
    :param exchange: The name of the exchange
    :type exchange: str
    :param interval: The interval of the data
    :type interval: str
    """
    history = load_history(exchange, interval)
    history.history[pair] = record
    history_file = paths.PAIR_DATA_DIR.joinpath(exchange, f"{interval}.json")
    history_file.write_text(history.json())


def delete_record(pair: str, exchange: str, interval: str):
    """
    Removes the pair record from the download history.

    :param pair: pair to remove
    :param exchange: exchange to remove
    :param interval: interval to remove
    """
    history = load_history(exchange, interval)
    history.history.pop(pair, None)
    history_file = paths.PAIR_DATA_DIR.joinpath(exchange, f"{interval}.json")
    history_file.write_text(history.json())


def get_pair_time_range(pair: str, interval: str, exchange: str):
    """
    It loads the data for the specified pair and interval from the specified exchange

    :param pair: The pair to get the time range for
    :type pair: str
    :param interval: The time interval between each data point
    :type interval: str
    :param exchange: The exchange to get the historical data for
    :type exchange: str
    :return: A tuple of two datetime objects.
    """
    logger.debug(f"Getting time range for {pair} on {exchange}")
    df = load_pair_history(
        pair,
        interval,
        paths.USER_DATA_DIR.joinpath("data", exchange),
    )
    if df.empty:
        logger.debug(f"No data found for {pair} on {exchange}")
        return None, None
    start_date: datetime = df.iloc[0]["date"].to_pydatetime().replace(tzinfo=utc)
    end_date: datetime = df.iloc[-1]["date"].to_pydatetime().replace(tzinfo=utc)
    return start_date, end_date


def update_download_history(
    requested_start_date: datetime,
    pairs: list[str],
    intervals: str,
    exchange: str,
):
    """
    Updates the download history with the actual start date.

    :param requested_start_date: requested start date
    :param pairs: list of pairs
    :param intervals: a list of intervals e.g. ['1m', '5m']
    :param exchange: exchange
    :return: None
    """
    for interval in intervals.split():
        for pair in pairs.copy():
            start_date, end_date = get_pair_time_range(pair, interval, exchange)
            if not start_date:
                delete_record(pair, exchange, interval)
                logger.debug(
                    "Failed to load dates for pair {} @ interval {}".format(pair, interval)
                )
                pairs.remove(pair)
                continue
            record = DownloadRecord(
                requested_start_date=requested_start_date,
                actual_start_date=start_date,
                end_date=end_date,
            )
            save_record(pair, record, exchange, interval)
    logger.debug(f'Download history updated for {" ".join(pairs)} @ {intervals}')


def remove_pair_record(
    pair: str, strategy: str, params: Union[HyperoptParameters, BacktestParameters]
):
    """
    Removes the pair record from the download history.

    :param pair: pair to remove
    :param strategy: strategy to remove
    :param params: HyperoptParameters or BacktestParameters
    """
    intervals, _ = load_informative_intervals_and_pairs_from_strategy(
        params.to_config_dict(strategy), params.pairs, params.timeframe_detail
    )
    for interval in intervals:
        delete_record(pair, params.config.exchange, interval)


def check_if_download_is_needed(
    exchange: str,
    pair: str,
    interval: str,
    requested_start_date: datetime,
    requested_end_date: Optional[datetime] = None,
) -> bool:
    """
    Check if the pair is already downloaded.

    :param exchange: Exchange name
    :param pair: Pair name. Example: BTC/USDT
    :param interval: Interval name
    :param requested_start_date: Start date of the download
    :param requested_end_date: End date of the download
    :return: True if the pair needs to be downloaded
    """
    # first check if pair file exists for the requested interval
    # example of pairfile: BTC_USDT-1m.json.
    # The forward slash is needs to be replaced with an underscore
    pair_file = paths.PAIR_DATA_DIR.joinpath(exchange, f'{pair.replace("/", "_")}-{interval}.json')
    need_pair_file = not pair_file.exists()
    # replace all dates with UTC
    logger.debug(f"Checking if download is needed for {pair} @ {interval}")
    # Check if the pair is already downloaded
    download_history = load_history(exchange, interval).history
    if pair not in download_history:
        logger.debug("Pair not in download history. Downloading.")
        return True
    logger.debug(f"Download history for {pair}: {download_history[pair].json()}")
    download_record = download_history[pair]

    # check if the pair has reached the first candle
    needs_beginning_candles = (
        requested_start_date < download_record.actual_start_date
        and not download_record.reached_first_candle
    )
    logger.debug(f"{pair} needs beginning candles: {needs_beginning_candles}")
    # make sure the difference between the requested end date and the actual end date is less than max_end_gap
    # if the requested end date is None, then we don't care about the end date

    max_end_gap = timedelta(days=2, hours=12)
    if requested_end_date is not None:
        needs_end_candles = (
            requested_end_date > download_record.end_date
            and requested_end_date - download_record.end_date > max_end_gap
        )
    else:
        needs_end_candles = False
    logger.debug(f"{pair} needs end candles: {needs_end_candles}")

    return need_pair_file or needs_beginning_candles or needs_end_candles


def download_data_for_strategy(
    strategy: str,
    config: Config,
    parameters: Union[BacktestParameters, HyperoptParameters],
):
    """
    It downloads the data for the given strategy, if it's not already downloaded

    :param strategy: The strategy to download data for
    :type strategy: str
    :param config: Config
    :type config: Config
    :param parameters: Union[BacktestParameters, HyperoptParameters]
    :type parameters: Union[BacktestParameters, HyperoptParameters]
    """
    intervals, pairs = load_informative_intervals_and_pairs_from_strategy(
        parameters.to_config_dict(strategy),
        parameters.pairs,
        parameters.timeframe_detail,
    )
    download_missing_historical_data(
        config, intervals, pairs + parameters.pairs, parameters.timerange
    )


def download_data_with_parameters(
    strategy: str,
    parameters: Union[BacktestParameters, HyperoptParameters],
):
    intervals, pairs = load_informative_intervals_and_pairs_from_strategy(
        parameters.to_config_dict(strategy),
        parameters.pairs,
        parameters.timeframe_detail,
    )
    download_missing_historical_data(parameters.config, intervals, pairs, parameters.timerange)


def download_data_with_config(
    lft_config: dict,
    timerange: str,
):
    loaded_intervals, loaded_pairs = load_informative_intervals_and_pairs_from_strategy(
        lft_config,
        lft_config["pairs"],
        lft_config.get("timeframe_detail"),
    )
    download_missing_historical_data(lft_config, loaded_intervals, loaded_pairs, timerange)


def download_missing_historical_data(
    config: Config,
    intervals: list[str],
    pairs: list[str],
    timerange: str,
):
    """
    It checks if the data is already downloaded for the given
    pairs and intervals. If not, it downloads the data

    :param intervals: list of intervals to download
    :param pairs: list of pairs to download
    :param config: Config object
    :param timerange: timerange to download
    """
    start_date, end_date = timerange.split("-")
    start_date = dateutil.parser.parse(start_date).replace(tzinfo=utc)
    if end_date:
        end_date = dateutil.parser.parse(end_date).replace(tzinfo=utc)
    else:
        end_date = datetime.now().replace(tzinfo=utc)
    pairs_to_download = set()
    tf_to_download = set()
    pair_list = pairs

    logger.info(
        f"Checking if download is needed for "
        f'{", ".join(pair_list)} @ '
        f'{", ".join(intervals)} interval(s)'
    )
    for interval in intervals:
        for pair in pair_list:
            logger.debug(f"Checking {pair} @ {interval}")
            if check_if_download_is_needed(config.exchange, pair, interval, start_date, end_date):
                logger.debug(f"Download needed for {pair} @ {interval}")
                pairs_to_download.add(pair)
                tf_to_download.add(interval)
    if pairs_to_download:
        logger.debug(f"Downloading missing data for {pairs_to_download}")
        # create datetime string in the YYYYMMDD format from the start date
        start_date_str = start_date.strftime("%Y%m%d-")
        queue = Queue()

        thread = Thread(
            target=download_watcher,
            args=(
                queue,
                start_date,
                len(pairs_to_download),
                tf_to_download,
                config.exchange,
            ),
            daemon=True,
        )
        thread.start()
        download(
            config,
            " ".join(tf_to_download),
            pairs=list(pairs_to_download),
            timerange=start_date_str,
            queue=queue,
        )
        thread.join()
        logger.info(
            "Finished downloading data for {} pairs @ {}",
            len(pairs_to_download),
            " ".join(tf_to_download),
        )

        def update_pairs():
            """
            This will wait for some time and then update the pair records.
            This is because freqtrade will not immediately update the pair data file
            after the download is finished.
            """
            time.sleep(3)
            update_download_history(
                start_date,
                list(pairs_to_download),
                ' '.join(tf_to_download),
                exchange=config.exchange,
            )

        Thread(target=update_pairs, daemon=True).start()
    logger.info("Data is up to date")


def download(
    config: Config,
    interval: str,
    days=None,
    pairs: list[str] = None,
    timerange: Optional[str] = None,
    secrets_config=None,
    queue: Queue = None,
):
    """
    Args:
        config: A config file object
        pairs: A list of pairs
        interval: The ticker interval. Default: 5m
        days: How many days worth of data to download
        timerange: Optional timerange parameter
        secrets_config: Optional secrets config file
        queue: Optional queue to put the data into

    Returns: A queue that takes in output from the downloader
    """
    assert days or timerange
    if not pairs:
        pairs = config.whitelist
    if timerange:
        start, _ = timerange.split("-")
        start_dt = dateutil.parser.parse(start)
        days_between = (datetime.now() - start_dt).days
        days = days_between
    logger.info(
        "Downloading {} days worth of market data for {} @ {} ticker-interval(s)...",
        days,
        " ".join(pairs),
        interval,
    )
    command = "download-data --days {} -c {} -p {} -t {} --userdir {} {}".format(
        days,
        config,
        " ".join(pairs),
        interval,
        USER_DATA_DIR,
        f"-c {secrets_config}" if secrets_config else "",
    ).split()
    sh.freqtrade(
        *command,
        _err=queue.put if queue else None,
        _out=queue.put if queue else None,
    )


def download_pair(pair: str, exchange: str, intervals: list[str], timerange: str):
    """
    It downloads the data for the specified pair, exchange, and intervals

    :param pair: The pair to download
    :type pair: str
    :param exchange: The exchange you want to download from
    :type exchange: str
    :param intervals: A list of intervals to download
    :type intervals: list[str]
    :param timerange: The time range to download data for
    :type timerange: str
    """
    config = Config(exchange + ".json")
    download_missing_historical_data(config, intervals, [pair], timerange)


def download_watcher(
    queue: Queue,
    start_date: datetime,
    n_pairs: int,
    timeframes: set[str],
    exchange: str,
):
    """
    It iterates over the number of pairs,
    and downloads the data for each pair. It then updates the download history

    :param queue: Queue to put the output into
    :param start_date: The start date to download data for
    :param n_pairs: The number of pairs to download
    :param timeframes: The timeframes to download
    :param exchange: The exchange to download from
    """
    pair_idx = 0
    timeframe_idx = 0
    # downloaded_pairs = []
    with alive_progress.alive_bar(n_pairs, title="Downloading pair data", force_tty=True) as bar:
        while pair_idx < n_pairs:
            try:
                output: str = queue.get(timeout=300)
            except Empty:
                logger.error(f"Downloader is not responding. Aborting.")
                break

            exec_log.info(output.strip())
            if "Closing async ccxt session" in output:
                break
            if "Downloaded data" not in output:
                continue
            timeframe_idx += 1
            # Downloaded data for AVAX/USDT with length 1877
            pair = output.split("Downloaded data for ")[1].split(" with length ")[0]
            if timeframe_idx == len(timeframes):
                # downloaded_pairs.append(pair)
                print(
                    "Downloaded history for {} @ {} ({}/{})".format(
                        pair,
                        ", ".join(timeframes),
                        pair_idx + 1,
                        n_pairs,
                    ),
                    end="",
                )
                pair_idx += 1
                timeframe_idx = 0
                bar()
