import datetime

from lazyft.config import Config


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
    if exchange == 'kucoin':
        return Config('kucoin_refresh_nov4.json')
    elif exchange == 'binance':
        return Config('binance_refresh_december.json')
