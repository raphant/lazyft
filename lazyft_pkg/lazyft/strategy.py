import tempfile
from pathlib import Path

import sh
import yaml

from lazyft.config import Config
from lazyft.paths import STRATEGY_DIR, USER_DATA_DIR
from lazyft.regex import strategy_files_pattern


class Strategy:
    metadata_file = STRATEGY_DIR.joinpath('metadata.yaml')

    @staticmethod
    def metadata() -> dict:
        if not Strategy.metadata_file.exists():
            return {}
        with Strategy.metadata_file.open('r') as f:
            return yaml.load(f)

    @staticmethod
    def add_pairs_to_blacklist(self, strategy: str, *pairs: str):
        existing = Strategy.metadata().get(strategy, {})
        blacklist = set(existing.get('blacklist', []))
        blacklist.update(pairs)
        existing[self.strategy_name] = list(blacklist)
        self.save_metadata(existing)

    @staticmethod
    def add_pairs_to_whitelist(strategy: str, *pairs: str):
        existing = Strategy.metadata().get(strategy, {})
        whitelist = set(existing.get('whitelist', []))
        whitelist.update(pairs)
        existing[strategy] = list(whitelist)

        Strategy.save_metadata(existing)

    @staticmethod
    def save_metadata(existing):
        with Strategy.metadata_file.open('w') as f:
            yaml.dump(existing, f)

    @staticmethod
    def get_blacklist(strategy):
        if strategy not in Strategy.metadata():
            return []
        Strategy.metadata()[strategy].get('blacklist', [])

    @staticmethod
    def get_whitelist(strategy):
        if strategy not in Strategy.metadata():
            return []
        Strategy.metadata()[strategy].get('whitelist', [])

    @staticmethod
    def init_config(config: Config, strategy: str):

        whitelist = Strategy.get_whitelist(strategy)
        blacklist = Strategy.get_blacklist(strategy)

        temp_path = tempfile.mkdtemp()
        tmp = Path(temp_path, 'config.json')
        tmp_config = Config(config.save(save_as=tmp))
        tmp_config.update_whitelist(whitelist, True)
        tmp_config.update_blacklist(blacklist, True)
        tmp_config.save()
        return tmp_config

    @staticmethod
    def get_file_name(strategy: str) -> str:
        """Returns the file name of a strategy"""
        to_dict = Strategy.get_all_strategies()
        return to_dict.get(strategy)

    @staticmethod
    def get_all_strategies():
        text = sh.freqtrade(
            'list-strategies', no_color=True, userdir=str(USER_DATA_DIR)
        )
        return dict(strategy_files_pattern.findall('\n'.join(text)))

    @staticmethod
    def create_strategy_params_filepath(strategy: str) -> Path:
        """Return the path to the strategies parameter file."""
        return STRATEGY_DIR.joinpath(
            Strategy.get_file_name(strategy).rstrip('.py') + '.json'
        )
