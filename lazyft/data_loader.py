from typing import Union

import pandas as pd
from diskcache import Cache
from freqtrade.configuration import TimeRange
from freqtrade.data.history import load_pair_history
from freqtrade.strategy import merge_informative_pair

from lazyft import logger, paths
from lazyft.config import Config
from lazyft.downloader import download_pair
from lazyft.paths import PAIR_DATA_DIR
from lazyft.strategy import load_strategy

cache = Cache(paths.CACHE_DIR)


def load_pair_data(
    pair: str, timeframe: str, config: Config, timerange=None,
    startup_candles=0,

) -> pd.DataFrame:
    """
    Loads the pair from the exchange and returns a pandas dataframe

    :param pair: The pair to load
    :param timeframe: The timeframe to load
    :param config: The config object
    :param timerange: The timerange to load data for
    :param startup_candles: The number of candles to load before the timerange
    :return: A DataFrame with the OHLCV data.
    """

    @cache.memoize(expire=60 * 30, tag="data_loader.load_pair_data")
    def func(pair, timeframe, exchange, timerange):
        if timerange:
            download_pair(pair.upper(), intervals=[timeframe], timerange=timerange, config=config)
        return load_pair_history(
            datadir=PAIR_DATA_DIR.joinpath(exchange),
            timeframe=timeframe,
            pair=pair.upper(),
            data_format="json",
            timerange=TimeRange.parse_timerange(timerange) if timerange else None,
            startup_candles=startup_candles,
        )

    data = func(pair, timeframe, config.exchange, timerange)
    assert not data.empty, f"Data for {pair} {timeframe} {config.exchange} {timerange} is empty"
    logger.info(
        f'Loaded {len(data)} rows for {pair} @ timeframe {timeframe}, data starts at '
        f'{data.iloc[0]["date"]}'
    )
    return data


def load_and_populate_pair_data(
    strategy_name: str, pair: str, timeframe: str, config: Config, timerange=None
) -> pd.DataFrame:
    """
    Loads pair data, populates indicators, and returns the dataframe

    :param strategy_name: The name of the strategy to load
    :param pair: The pair to load data for
    :param timeframe: The timeframe to load data for
    :param config: The config object
    :param timerange: A TimeRange object
    :return: A dataframe with the populated data
    """
    data = load_pair_data(pair, timeframe, config, timerange=timerange)
    from lazyft import BASIC_CONFIG

    strategy = load_strategy(strategy_name, BASIC_CONFIG)
    populated = strategy.advise_all_indicators({pair: data})
    return populated[pair]


def load_pair_data_for_each_timeframe(
    pair: str, timerange: str, timeframes: list[str], config: Config, column=None
) -> Union[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    Loads the data for a given pair, for each timeframe in the given list of timeframes, for the given
    timerange. If a column is specified, the data is returned as a DataFrame with the approriate
    "{column}_{timeframe}" column for each dataframe.

    :param pair: The pair you want to load data for
    :param timerange: the range of time to load data for
    :param timeframes: list of timeframes to load data for
    :param config: the config object
    :param column: the column to load data for.
    :return: A list of dataframes
    """
    merged = load_pair_data(pair, timeframes[0], config, timerange=timerange)
    for tf in timeframes[1:]:
        merged = merge_informative_pair(
            merged, load_pair_data(pair, tf, config, timerange=timerange), timeframes[0], tf
        )
    logger.info(merged.describe())
    if column:
        # get all columns in merged that contain the column
        columns = [col for col in merged.columns if column in col]
        df_with_columns = merged[columns]
        return df_with_columns
    return merged


if __name__ == "__main__":
    print(load_pair_data_for_each_timeframe("BTC/USDT", "20220101-", ["1h", "2h", "4h", "8h"]))
