import tempfile
from pathlib import Path

import yaml

from lazyft.config import Config
from lazyft.constants import STRATEGY_DIR


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
        temp_path = tempfile.mkdtemp()

        whitelist = Strategy.get_whitelist(strategy)
        blacklist = Strategy.get_blacklist(strategy)

        tmp = Path(temp_path, 'config.json')
        tmp_config = Config(config.save(save_as=tmp))
        tmp_config.update_whitelist(whitelist, True)
        tmp_config.update_blacklist(blacklist, True)
        tmp_config.save()
        return tmp_config
