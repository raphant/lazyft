from __future__ import annotations

import os
import pathlib
import tempfile
from pathlib import Path
from typing import Union, Iterable

import rapidjson
from freqtrade.configuration import Configuration

from lazyft import logger
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
        return self._data['exchange']['name']

    def save(self, save_as: Union[os.PathLike, str] = None) -> Path:
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
            save_as = CONFIG_DIR.joinpath(Path(save_as).name)
        if save_as.exists():
            logger.info(f'Overwriting {save_as}')
        save_as.write_text(self.to_json)
        return save_as

    def tmp(self):
        temp_path = tempfile.mkdtemp()
        tmp = Path(temp_path, 'config.json')
        return Config(self.save(save_as=tmp))

    def update_whitelist_and_save(self, whitelist: Iterable[str], append=False) -> list[str]:
        if append:
            existing = set(self['exchange']['pair_whitelist'])
            existing.update(whitelist)
            self['exchange']['pair_whitelist'] = list(existing)
        else:
            self['exchange']['pair_whitelist'] = whitelist
        self.save()
        return self['exchange']['pair_whitelist']

    def update_blacklist(self, blacklist: Iterable[str], append=False) -> list[str]:
        if append:
            existing = set(self['exchange'].get('pair_blacklist', []))
            existing.update(blacklist)
            self['exchange']['pair_blacklist'] = list(existing)
        else:
            self['exchange']['pair_blacklist'] = blacklist
        return self['exchange']['pair_blacklist']

    @property
    def whitelist(self):
        return self.data['exchange']['pair_whitelist']

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
    def new(cls, config_name: str, from_config: Union[str, 'Config']) -> 'Config':
        """
        Creates a new config file from an existing one.
        Args:
            config_name: The name of the new config file name
            from_config: The exising config file to copy. Can be a Config object or a string.

        Returns: The new Config file

        """
        return cls(cls(str(from_config)).save(config_name))

    def get(self, key, default=None):
        return self._data.get(key, default)

    def copy(self) -> 'Config':
        """Returns a temporary copy of the config"""
        from_path = self._config_path
        tmp_dir = tempfile.mkdtemp()
        to_path = pathlib.Path(tmp_dir, self._config_path.name)
        to_path.write_text(from_path.read_text())
        return Config(to_path)

    def update(self, update: dict):
        self._data.update(update)

    def to_configuration(self):
        return Configuration.from_files([str(self._config_path)])

    def __getitem__(self, key: str):
        if key == 'starting_balance':
            logger.warning('"{}" -> "dry_run_wallet"', key)
            key = 'dry_run_wallet'

        return self._data[key]

    def __setitem__(self, key: str, item: object):
        if key == 'starting_balance':
            logger.warning('"{}" -> "dry_run_wallet"', key)
            key = 'dry_run_wallet'

        self._data[key] = item

    def __str__(self) -> str:
        return str(self.path)

    def __repr__(self) -> str:
        return str(self.path)


if __name__ == '__main__':
    c = Config('/home/raphael/PycharmProjects/freqtrade/config1.json')
    c['max_open_trades'] = 500
    new_path = c.save('config1.json')
    print(c.data)
    print(new_path)
