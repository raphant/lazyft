from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import dateutil.parser
import rapidjson
import sh
from arrow import Arrow
from freqtrade.exchange import Exchange
from freqtrade.plugins.pairlistmanager import PairListManager

from lazyft import logger
from lazyft.config import Config
from lazyft.paths import USER_DATA_DIR

STABLE_COINS = ['USDT', 'USDC', 'BUSD', 'USD']
blacklist = [
    "^(BNB|BTC|ETH)/.*",
    "^(.*USD.*|PAX|PAXG|DAI|IDRT|AUD|BRZ|CAD|CHF|EUR|GBP|HKD|JPY|NGN|RUB|SGD|TRY|UAH|VAI|ZAR)/.*",
    ".*(_PREMIUM|BEAR|BULL|DOWN|HALF|HEDGE|UP|[1235][SL])/.*",
    ".*(ACM|AFA|ALA|ALL|APL|ASR|ATM|BAR|CAI|CITY|FOR|GAL|GOZ|IBFK|JUV|LEG|LOCK-1|NAVI|NOV|OG|PFL|PSG|ROUSH|STV|TH|TRA|UCH|UFC|YBO)/.*",
    "^(CVP|NMR)/.*",
    "^(ATOM)/.*",
]


class QuickTools:
    @staticmethod
    def get_timerange(config: Config, days: int, interval: str) -> Tuple[str, str]:
        """

        Args:
            config: A config file object
            days: How many days to split
            interval: The ticker interval. Default: 5m


        Returns: Tuple of a hyperopt timerange and a backtest timerange

        Takes N days and splits those days into ranges of 2/3rds for hyperopt and 1/3rd for
        backtesting
        """
        first_date, last_date = QuickTools.get_first_last_date_of_pair_data(
            config, interval
        )
        if days and last_date.shift(days=-days) > first_date:
            first_date = last_date.shift(days=-days)
        days_between = abs((first_date - last_date).days)

        two_thirds = round(days_between * (2 / 3))
        start_range = (first_date, first_date.shift(days=two_thirds))
        end_range = (start_range[1].shift(days=0), last_date)
        hyperopt_range = f"{'-'.join([s.format('YYYYMMDD') for s in start_range])}"
        backtest_range = f"{'-'.join([s.format('YYYYMMDD') for s in end_range])}"
        return hyperopt_range, backtest_range

    @staticmethod
    def get_first_last_date_of_pair_data(
        config: Config, interval: str
    ) -> Tuple[Arrow, Arrow]:
        """

        Args:
            config: A config file object
            interval: The ticker interval. Default: 5m

        Returns: The first and last day of data stored as Arrow objects

        """
        pair: str = config.whitelist[0]
        pair = pair.replace('/', '_') + f'-{interval}' + '.json'
        logger.debug('Getting time-ranges using {}', pair)
        exchange = config['exchange']['name']
        infile = Path(USER_DATA_DIR, f'data/{exchange}', pair)
        # load data
        data = rapidjson.load(infile.open(), number_mode=rapidjson.NM_NATIVE)
        import pandas as pd

        df = pd.DataFrame(
            data=data, columns=['open_time', 'open', 'high', 'low', 'close', 'volume']
        )
        df['open_time'] = df['open_time'] / 1000
        last_date = Arrow.fromtimestamp(df.iloc[-1]['open_time'], tzinfo='utc')
        first_date = Arrow.fromtimestamp(df.iloc[0]['open_time'], tzinfo='utc')
        return first_date, last_date

    # @staticmethod
    # def change_pairs(
    #     config_path: PathLike, pairs_name, pair_names_json='pair-names.json'
    # ):
    #     config = rapidjson.loads(Path(config_path).read_text())
    #     pairlist_names = rapidjson.loads(Path(pair_names_json).read_text())
    #     try:
    #         pairlist = pairlist_names[pairs_name]
    #     except KeyError:
    #         print(f'\nCould not find pairlist: "{pairs_name}"')
    #         return exit(1)
    #     config['exchange']['pair_whitelist'] = pairlist['list']
    #     QuickTools.save_config(config, config_path)
    #
    # @staticmethod
    # def save_config(config: dict, config_path: PathLike):
    #     """
    #
    #     Args:
    #         config:
    #         config_path:
    #
    #     Returns:
    #
    #     """
    #     path = Path(config_path)
    #     with open(path, 'w') as f:
    #         rapidjson.dump(config, f, indent=2)

    @staticmethod
    def refresh_pairlist(
        config: Config, n_coins: int, save_as=None, age_limit=14, **kwargs
    ) -> list[str]:
        default_kwargs = dict(
            PriceFilter=True,
            AgeFilter=True,
            SpreadFilter=True,
            RangeStabilityFilter=True,
            VolatilityFilter=True,
        )
        logger.info('Refreshing pairlist...')
        default_kwargs.update(kwargs)
        QuickTools.set_pairlist_settings(config, n_coins, age_limit, **default_kwargs)
        exchange = Exchange(config.data)
        manager = PairListManager(exchange, config.data)
        try:
            manager.refresh_pairlist()
        finally:
            config.update_whitelist(manager.whitelist)
            config['pairlists'].clear()
            config['pairlists'].append({"method": "StaticPairList"})
            config.save(save_as)
        logger.info('Finished refreshing pairlist')
        return manager.whitelist

    @staticmethod
    def set_pairlist_settings(config: Config, n_coins, age_limit, **filter_kwargs):
        """

        Args:
            config: A config file object
            n_coins: The number of coins to get
            age_limit: Filter the coins based on an age limit

        Returns: None

        """
        config['exchange']['pair_whitelist'] = []
        config['pairlists'][0] = {
            "method": "VolumePairList",
            "number_assets": n_coins,
            "sort_key": "quoteVolume",
            "refresh_period": 1800,
        }
        if filter_kwargs['AgeFilter']:
            config['pairlists'].append(
                {"method": "AgeFilter", "min_days_listed": age_limit}
            )
        if filter_kwargs['PriceFilter']:
            config['pairlists'].append({"method": "PriceFilter", "min_price": 0.001})
        if filter_kwargs['SpreadFilter']:
            config['pairlists'].append(
                {"method": "SpreadFilter", "max_spread_ratio": 0.005}
            )
        if filter_kwargs['RangeStabilityFilter']:
            config['pairlists'].append(
                {
                    "method": "RangeStabilityFilter",
                    "lookback_days": 3,
                    "min_rate_of_change": 0.1,
                    "refresh_period": 1440,
                }
            )
        if filter_kwargs['VolatilityFilter']:
            config['pairlists'].append(
                {
                    "method": "VolatilityFilter",
                    "lookback_days": 3,
                    "min_volatility": 0.02,
                    "max_volatility": 0.75,
                    "refresh_period": 86400,
                }
            )

        # set blacklist
        if config['stake_currency'] in STABLE_COINS:
            config['exchange']['pair_blacklist'] = blacklist

    @staticmethod
    def download_data(
        config: Config,
        interval: Optional[str],
        days=None,
        timerange: Optional[str] = None,
        verbose=False,
    ):
        """

        Args:
            config: A config file object
            interval: The ticker interval. Default: 5m
            days: How many days worth of data to download
            timerange: Optional timerange parameter
            verbose: Default: False

        Returns: None
        """

        def print_(text: str):
            if verbose:
                logger.info(text.strip())

        assert days or timerange

        if timerange:
            start, finish = timerange.split('-')
            start_dt = dateutil.parser.parse(start)
            days_between = (datetime.now() - start_dt).days
            days = days_between

        logger.info(
            'Downloading {} days worth of market data for {} coins @ {} ticker-interval',
            days,
            len(config.whitelist),
            interval,
        )
        command = 'download-data --days {} -c {} -t {} --userdir {}'.format(
            days, config, interval, USER_DATA_DIR
        ).split()
        sh.freqtrade(
            *command,
            _err=print_,
            _out=print_,
        )
        logger.info('Finished downloading data')


class PairListTools:
    pair_names_json = 'pair-names.json'
