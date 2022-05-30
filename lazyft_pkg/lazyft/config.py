from __future__ import annotations

import os
import pathlib
import tempfile
from pathlib import Path
from typing import Iterable, Union

import rapidjson
from freqtrade.commands.build_config_commands import ask_user_overwrite
from freqtrade.configuration import Configuration
from freqtrade.exceptions import OperationalException
from freqtrade.exchange import validate_exchange, validate_exchanges
from lazyft import BASIC_CONFIG, logger
from lazyft.paths import CONFIG_DIR


class Config:
    """
    A wrapper for a FreqTrade config file.
    Can be used like `config[key] = value` to get and set values.
    """

    def __init__(self, path: Union[os.PathLike, str]) -> None:
        """
        Args:
            path: A path to or the name of an existing config file.
                MAIN_DIR/config/ directory will be prepended to the config file name if no
                path is included.
        """
        temp = Path(path)
        if temp.exists():
            self._config_path = temp.resolve()
        else:
            self._config_path = Path(CONFIG_DIR, path).resolve()
            assert self._config_path.exists(), f'"{self._config_path}" doesn\'t exist'
        self._data: dict = rapidjson.loads(self._config_path.read_text())

    @property
    def exchange(self):
        return self._data["exchange"]["name"]

    def save(self, save_as: Union[os.PathLike, str] = None, overwrite=False) -> Path:
        """
        Saves the config to a file. The config will be saved to the `./config` directory.

        :param save_as: An optional path to save the config file to. Only include the file name,
            not the directory.
        :return: The path to the saved config file.
        """
        if save_as is None:
            save_as = self._config_path
        else:
            # create a path object from the string, and grab the file name
            if isinstance(save_as, str):
                save_as = Path(save_as)
            save_as = CONFIG_DIR.joinpath(save_as.name)
            if save_as.exists():
                overwrite = (
                    overwrite
                    or input(f"{save_as} already exists. Overwrite? [y/n] ").lower()
                    == "y"
                )
                if overwrite:
                    logger.info(f"Overwriting {save_as}")
                else:
                    raise OperationalException(
                        f"Configuration file `{save_as}` already exists. "
                        "Please delete it or use a different configuration file name."
                    )
        save_as.write_text(self.to_json)
        return save_as

    def tmp(self):
        temp_path = tempfile.mkdtemp()
        tmp = Path(temp_path, "config.json")
        return Config(self.save(save_as=tmp))

    def update_whitelist_and_save(
        self, whitelist: Iterable[str], append=False
    ) -> list[str]:
        if append:
            existing = set(self["exchange"]["pair_whitelist"])
            existing.update(whitelist)
            self["exchange"]["pair_whitelist"] = list(existing)
        else:
            self["exchange"]["pair_whitelist"] = whitelist
        self.save()
        return self["exchange"]["pair_whitelist"]

    def update_blacklist(self, blacklist: Iterable[str], append=False) -> list[str]:
        if append:
            existing = set(self["exchange"].get("pair_blacklist", []))
            existing.update(blacklist)
            self["exchange"]["pair_blacklist"] = list(existing)
        else:
            self["exchange"]["pair_blacklist"] = blacklist
        return self["exchange"]["pair_blacklist"]

    @property
    def whitelist(self) -> list[str]:
        return self.data["exchange"]["pair_whitelist"]

    @property
    def to_json(self) -> str:
        """
        Returns: A valid JSON string
        """
        return rapidjson.dumps(self._data, indent=2)

    @property
    def data(self):
        """
        Returns: A copy of the config data as a `dict`.
        """
        return self._data.copy()

    @property
    def path(self):
        return self._config_path

    @classmethod
    def new(
        cls, config_path: Union[str, Path], from_config: Union[str, "Config"]
    ) -> "Config":
        """
        Creates a new config file from an existing one.

        :param config_path: The path to the new config file.
        :param from_config: The path to the existing config file, or a `Config` object.
        :return: A new `Config` object.
        """
        if isinstance(from_config, str):
            from_config = Config(from_config)
        assert from_config.path.exists(), f'"{from_config.path}" doesn\'t exist'
        return Config(from_config.save(save_as=CONFIG_DIR / config_path))

    def get(self, key, default=None):
        return self._data.get(key, default)

    def copy(self) -> "Config":
        """Returns a temporary copy of the config"""
        from_path = self._config_path
        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir, from_path.name)
        return Config.new(config_path=tmp_path, from_config=self)

    def update(self, update: dict):
        self._data.update(update)

    @classmethod
    def from_ft_config(cls, ft_config: dict, path: str):
        pass

    def to_configuration(self):
        return Configuration.from_files([str(self._config_path)])

    def __getitem__(self, key: str):
        if key == "starting_balance":
            logger.warning('"{}" -> "dry_run_wallet"', key)
            key = "dry_run_wallet"

        return self._data[key]

    def __setitem__(self, key: str, item: object):
        if key == "starting_balance":
            logger.warning('"{}" -> "dry_run_wallet"', key)
            key = "dry_run_wallet"

        self._data[key] = item

    def __str__(self) -> str:
        return str(self.path)

    def __repr__(self) -> str:
        return str(self.path)


def create_new_config_for_exchange(
    exchange_name: str,
    config_path: Union[Path, str],
    stake_currency: str,
    base_config: Union[Path, str] = None,
    do_refresh_pairlist: bool = True,
    n_coins: int = 30,
) -> Config:
    try:
        valid, reason = validate_exchange(exchange_name)
    except AttributeError:
        raise ValueError(f"{exchange_name} is not a valid exchange name in ccxt")
    assert valid, f"{exchange_name} is not a valid exchange: {reason}"
    if base_config:
        logger.info(f'Creating new config for "{exchange_name}" from "{base_config}"')
        new_config = Config.new(config_path, base_config)
    else:
        if config_path.exists():
            overwrite = ask_user_overwrite(config_path)
            if overwrite:
                config_path.unlink()
                logger.info(f"Overwriting config file: {config_path}")
            else:
                raise OperationalException(
                    f"Configuration file `{config_path}` already exists. "
                    "Please delete it or use a different configuration file name."
                )
        new_config = Config.new(config_path, BASIC_CONFIG)

        # update exchange name
        new_config["exchange"]["name"] = exchange_name
        new_config["stake_currency"] = stake_currency
        new_config.save()
        # refresh pairlist
    if do_refresh_pairlist:
        from lazyft.pairlist import refresh_pairlist

        pairs = refresh_pairlist(new_config, n_coins=n_coins)
        logger.info(
            f"Generated pairlist for {exchange_name}. Pairlist length: {len(pairs)}"
        )
    logger.info(f"Created new config file: {config_path}")
    return new_config


if __name__ == "__main__":
    # c = Config('/home/raphael/PycharmProjects/freqtrade/config1.json')
    # c['max_open_trades'] = 500
    # new_path = c.save('config1.json')
    # print(c.data)
    # print(new_path)
    print(
        create_new_config_for_exchange(
            "binanceus", "config.binanceus.json", "config_binance.us.json", n_coins=40
        )
    )
