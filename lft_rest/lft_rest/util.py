import datetime
from rapidjson import JSONDecodeError

from lazyft.config import Config
from lft_rest import logger


def get_timerange(days):
    """
    get last 7 days in format YYYYMMDD-YYYYMMDD

    :param days: number of days
    :return:
    """
    start = datetime.datetime.now() - datetime.timedelta(days=days)
    end = datetime.datetime.now()
    return f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"


def get_config(exchange: str):
    logger.info(f"Getting config for {exchange}")
    try:
        if exchange == 'kucoin':
            return Config('kucoin_refresh_nov4.json')
        elif exchange == 'binance':
            return Config('binance_refresh_december.json')
    except JSONDecodeError as e:
        raise Exception(f"Error loading config for {exchange}: {e}")
