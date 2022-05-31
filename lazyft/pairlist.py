from __future__ import annotations

from freqtrade.exchange import Exchange
from freqtrade.plugins.pairlistmanager import PairListManager

from lazyft import logger
from lazyft.config import Config
from lazyft.reports import get_hyperopt_repo

STABLE_COINS = ["USDT", "USDC", "BUSD", "USD"]
BLACKLIST = [
    "^(BNB|BTC|ETH)/.*",
    "^(.*USD.*|PAX|PAXG|DAI|IDRT|AUD|BRZ|CAD|CHF|EUR|GBP|HKD|JPY|NGN|RUB|SGD|TRY|UAH|VAI|ZAR)/.*",
    ".*(_PREMIUM|BEAR|BULL|DOWN|HALF|HEDGE|UP|[1235][SL])/.*",
    ".*(ACM|AFA|ALA|ALL|APL|ASR|ATM|BAR|CAI|CITY|FOR|GAL|GOZ|IBFK|JUV|LEG|LOCK-1|NAVI|NOV|OG|PFL|PSG|ROUSH|STV|TH|TRA|UCH|UFC|YBO)/.*",
    "^(CVP|NMR)/.*",
    "^(ATOM)/.*",
    "DOGE/USDT",
]


def load_pairlist_from_id(id: int):
    logger.debug("loading pairlist from params id {}", id)
    return get_hyperopt_repo().get_by_param_id(id).pairlist


def refresh_pairlist(
    config: Config, n_coins: int, save_as=None, age_limit=7, **kwargs
) -> list[str]:
    """
    Refresh the pairlist with the latest data from the exchange. Default settings are:
        `PriceFilter=True,
        AgeFilter=True,
        SpreadFilter=True,
        RangeStabilityFilter=True,
        VolatilityFilter=True`

    :param config: The original config to use settings from
    :param n_coins: The number of coins to include in the pairlist
    :param save_as: (optional) The name of the pairlist to save the new one as
    :param age_limit: (optional) The age limit for the coins to include in the pairlist
    :param kwargs: (optional) Any additional filters to apply to the pairlist
    :return: The new pairlist
    """
    logger.info("Refreshing pairlist...")
    # in case the user wants to save changes as a new config
    config_copy = config.copy()
    # these settings will be used to filter the pairlist
    filter_kwargs = dict(
        PriceFilter=True,
        AgeFilter=True,
        SpreadFilter=True,
        RangeStabilityFilter=True,
        VolatilityFilter=True,
    )
    filter_kwargs.update(kwargs)
    # update the config object with the new settings
    set_pairlist_settings(config_copy, n_coins, age_limit, **filter_kwargs)

    exchange = Exchange(config_copy.data)
    manager = PairListManager(exchange, config_copy.data)
    try:
        manager.refresh_pairlist()
    finally:
        config_copy.update_whitelist_and_save(manager.whitelist)
        reset_pairlist_settings(config_copy)
        config_copy.save(save_as)
    logger.info("Finished refreshing pairlist ({})", len(manager.whitelist))
    return manager.whitelist


def set_pairlist_settings(config: Config, n_coins, age_limit, **filter_kwargs):
    """
    Set the settings for the pairlist in the config object

    :param config: The config object to update
    :param n_coins: The number of coins to include in the pairlist
    :param age_limit: The age limit for the coins to include in the pairlist
    :param filter_kwargs: Any additional filters to apply to the pairlist
    :return: The updated config object
    """
    config["exchange"]["pair_whitelist"] = []
    config["pairlists"][0] = {
        "method": "VolumePairList",
        "number_assets": n_coins,
        "sort_key": "quoteVolume",
        "refresh_period": 1800,
    }
    if filter_kwargs["AgeFilter"]:
        config["pairlists"].append({"method": "AgeFilter", "min_days_listed": age_limit})
    if filter_kwargs["PriceFilter"]:
        config["pairlists"].append({"method": "PriceFilter", "min_price": 0.001})
    if filter_kwargs["SpreadFilter"]:
        config["pairlists"].append({"method": "SpreadFilter", "max_spread_ratio": 0.005})
    if filter_kwargs["RangeStabilityFilter"]:
        config["pairlists"].append(
            {
                "method": "RangeStabilityFilter",
                "lookback_days": 3,
                "min_rate_of_change": 0.05,
                "refresh_period": 1800,
            }
        )
    if filter_kwargs["VolatilityFilter"]:
        config["pairlists"].append(
            {
                "method": "VolatilityFilter",
                "lookback_days": 3,
                "min_volatility": 0.02,
                "max_volatility": 0.75,
                "refresh_period": 1800,
            }
        )

    # set blacklist
    if config["stake_currency"] in STABLE_COINS:
        config["exchange"]["pair_blacklist"] = BLACKLIST


def reset_pairlist_settings(config: Config):
    """
    Reset the pairlist settings to StaticPairList

    :param config: The config object to update
    :return: The updated config object
    """
    config["pairlists"] = [
        {
            "method": "StaticPairList",
        }
    ]
    return config
