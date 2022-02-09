from pathlib import Path
from typing import Any

import rapidjson

import logging
# from loguru import logger

logger = logging.getLogger(__name__)


class SpaceHandler:
    def __init__(self, strategy_path: str, disable=False) -> None:
        self.strategy_path = Path(strategy_path)
        self.settings_file_path = self.strategy_path.with_name(f'{self.strategy_path.stem}.sh.json')
        self._settings: dict[str, bool] = {}
        if disable:
            logger.info(f'Disabling space handler...')
            return
        self._load_settings()

    @property
    def all_enabled(self):
        return self._settings.get('all', False)

    def set_all_enabled(self):
        logger.info(f'Setting all spaces to enabled...')
        self._settings['all'] = True

    def _load_settings(self):
        if self.settings_file_path.exists():
            logger.info(f'Loading space settings from {self.settings_file_path}...')
            self._settings = rapidjson.loads(self.settings_file_path.read_text())
            if self._settings.get('all', False):
                self.enable_all()
        else:
            logger.info(f'No space settings found: {self.settings_file_path}')

    def get_space(self, key: str) -> bool:
        try:
            logger.debug(f'Getting space "{key}" status')
            return self._settings[key]
        except KeyError:
            logger.debug(f'"{key}" not found in spaces...')
            return self.all_enabled

    def get_setting(self, key: str, default=None):
        try:
            logger.debug(f'Getting space setting "{key}"')
            return self._settings[key]
        except KeyError:
            logger.debug(f'"{key}" not found in space settings...')
            return default

    def add_space(self, key: str):
        logger.info(f'Enabling space "{key}"...')
        self._settings[key] = True

    def add_setting(self, key: str, value: Any):
        logger.info(f'Adding space setting "{key}" with value "{value}"')
        self._settings[key] = value

    def reset(self):
        """
        Sets all keys to false
        :return:
        """
        for key in self._settings.keys():
            self._settings[key] = False

    def save(self):
        logger.info(f'Saving space settings to {self.settings_file_path}...')
        self.settings_file_path.write_text(rapidjson.dumps(self._settings))

    def enable_all(self):
        logger.info(f'Enabling all spaces...')
        for key in self._settings.keys():
            if key != 'all':
                self._settings[key] = True
