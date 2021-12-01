from datetime import datetime
from typing import Union, Optional

import dateutil.parser
import pytz
from freqtrade.data.history import load_pair_history
from pydantic import BaseModel

from lazyft import paths, logger
from lazyft.command_parameters import BacktestParameters, HyperoptParameters
from lazyft.config import Config
from lazyft.quicktools import QuickTools

if not paths.PAIR_DATA_DIR.exists():
    paths.PAIR_DATA_DIR.mkdir(parents=True)
utc = pytz.UTC


class DownloadRecord(BaseModel):
    requested_start_date: datetime
    actual_start_date: datetime
    end_date: datetime

    @property
    def reached_first_candle(self):
        """
        Returns True if the last requested start date is the before the actual start date.
        If this is True then the beginning of the pairs candle lifetime has been reached.
        """
        return self.requested_start_date > self.actual_start_date


class History(BaseModel):
    history: dict[str, DownloadRecord] = {}


def load_history(exchange: str, interval: str) -> History:
    """
    Load the download history from the file.
    """
    history_file = paths.PAIR_DATA_DIR.joinpath(exchange, f'{interval}.json')
    if not history_file.exists():
        history_file.write_text('{}')
    return History.parse_file(history_file)


def save_record(pair: str, record: DownloadRecord, exchange: str, interval: str):
    history = load_history(exchange, interval)
    history.history[pair] = record
    history_file = paths.PAIR_DATA_DIR.joinpath(exchange, f'{interval}.json')
    history_file.write_text(history.json())


def get_pair_time_range(pair: str, interval: str, exchange: str):
    df = load_pair_history(
        pair,
        interval,
        paths.USER_DATA_DIR.joinpath('data', exchange),
    )
    if df.empty:
        return None, None
    start_date: datetime = df.iloc[0]['date'].to_pydatetime().replace(tzinfo=utc)
    end_date: datetime = df.iloc[-1]['date'].to_pydatetime().replace(tzinfo=utc)
    return start_date, end_date


def update_download_history(
    requested_start_date: datetime,
    pairs: list[str],
    intervals: str,
    exchange: str,
):
    for interval in intervals.split():
        for pair in pairs:
            start_date, end_date = get_pair_time_range(pair, interval, exchange)
            record = DownloadRecord(
                requested_start_date=requested_start_date,
                actual_start_date=start_date,
                end_date=end_date,
            )
            save_record(pair, record, exchange, interval)
    logger.info(f'Download history updated for {pairs}')


def check_if_download_is_needed(
    exchange: str,
    pair: str,
    interval: str,
    requested_start_date: datetime,
    requested_end_date: Optional[datetime] = None,
) -> bool:
    """
    Check if the pair is already downloaded.
    """
    # replace all dates with UTC
    logger.debug(f'Checking if download is needed for {pair} @ {interval}')
    # Check if the pair is already downloaded
    download_history = load_history(exchange, interval).history
    if pair not in download_history:
        return True
    # check if the pair has reached the first candle
    download_record = download_history[pair]
    needs_beginning_candles = not download_record.reached_first_candle
    # check if the requested end date is greater than the pairs end date
    needs_end_date_candles = (
        requested_end_date
        and requested_end_date.date() > download_record.end_date.date()
    )
    # if requested_start_date is before the first candle, and the pairs beginning candles hasn't
    # been downloaded, we need to download
    return (
        requested_start_date < download_record.actual_start_date
        and needs_beginning_candles
    ) or needs_end_date_candles


def download_missing_historical_data(
    config: Config,
    parameters: Union[BacktestParameters, HyperoptParameters],
):

    timerange: str = parameters.timerange
    start_date, end_date = timerange.split('-')
    start_date = dateutil.parser.parse(start_date).replace(tzinfo=utc)
    if end_date:
        end_date = dateutil.parser.parse(end_date).replace(tzinfo=utc)
    else:
        end_date = datetime.now().replace(tzinfo=utc)
    to_download = set()
    for interval in parameters.intervals_to_download.split():
        for pair in parameters.pairs:
            if check_if_download_is_needed(
                config.exchange, pair, interval, start_date, end_date
            ):
                to_download.add(pair)
                break
    if to_download:
        logger.info(f"Downloading missing data for {to_download}")
        # create datetime string in the YYYYMMDD format from the start date
        start_date_str = start_date.strftime("%Y%m%d-")
        QuickTools.download_data(
            config,
            parameters.intervals_to_download,
            pairs=list(to_download),
            timerange=start_date_str,
        )
        update_download_history(
            start_date,
            list(to_download),
            parameters.intervals_to_download,
            config.exchange,
        )
