from __future__ import annotations

from datetime import datetime, timedelta
from typing import Tuple

from freqtrade.exchange import Exchange
from freqtrade.plugins.pairlistmanager import PairListManager

from lazyft import logger
from lazyft.config import Config

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
    def get_timerange(days: int) -> Tuple[str, str]:
        """

        Args:
            days: How many days to split
        Returns: Tuple of a hyperopt timerange and a backtest timerange

        Takes N days and splits those days into ranges of 2/3rds for hyperopt and 1/3rd for
        backtesting
        """
        today = datetime.now()
        start_day = datetime.now() - timedelta(days=days)
        hyperopt_days = round(days - days / 3)
        backtest_days = round(days / 3) - 1
        hyperopt_start, hyperopt_end = start_day, start_day + timedelta(days=hyperopt_days)
        backtest_start, backtest_end = (today - timedelta(days=backtest_days), today)

        hyperopt_range = f'{hyperopt_start.strftime("%Y%m%d")}-{hyperopt_end.strftime("%Y%m%d")}'
        backtest_range = f'{backtest_start.strftime("%Y%m%d")}-{backtest_end.strftime("%Y%m%d")}'
        return hyperopt_range, backtest_range

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
        config: Config, n_coins: int, save_as=None, age_limit=7, **kwargs
    ) -> list[str]:
        config_copy = config.copy()
        filter_kwargs = dict(
            PriceFilter=True,
            AgeFilter=True,
            SpreadFilter=True,
            RangeStabilityFilter=True,
            VolatilityFilter=True,
        )
        logger.info('Refreshing pairlist...')
        filter_kwargs.update(kwargs)
        set_pairlist_settings(config_copy, n_coins, age_limit, **filter_kwargs)
        exchange = Exchange(config_copy.data)
        manager = PairListManager(exchange, config_copy.data)
        try:
            manager.refresh_pairlist()
        finally:
            config.update_whitelist_and_save(manager.whitelist)
            config.save(save_as)
        logger.info('Finished refreshing pairlist ({})', len(manager.whitelist))
        return manager.whitelist


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
        config['pairlists'].append({"method": "AgeFilter", "min_days_listed": age_limit})
    if filter_kwargs['PriceFilter']:
        config['pairlists'].append({"method": "PriceFilter", "min_price": 0.001})
    if filter_kwargs['SpreadFilter']:
        config['pairlists'].append({"method": "SpreadFilter", "max_spread_ratio": 0.005})
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


class PairListTools:
    pair_names_json = 'pair-names.json'
