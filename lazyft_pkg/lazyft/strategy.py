import os
import tempfile
from pathlib import Path

import sh
import yaml

import lazyft.paths as paths
from lazyft import logger
from lazyft.config import Config
from lazyft.regex import strategy_files_pattern


class StrategyTools:
    metadata_file = paths.STRATEGY_DIR.joinpath("metadata.yaml")
    strategy_dict = None
    _last_strategy_len = None

    @staticmethod
    def metadata() -> dict:
        if not StrategyTools.metadata_file.exists():
            return {}
        with StrategyTools.metadata_file.open("r") as f:
            return yaml.load(f)

    @staticmethod
    def add_pairs_to_blacklist(self, strategy: str, *pairs: str):
        existing = StrategyTools.metadata().get(strategy, {})
        blacklist = set(existing.get("blacklist", []))
        blacklist.update(pairs)
        existing[self.strategy_name] = list(blacklist)
        self.save_metadata(existing)

    @staticmethod
    def add_pairs_to_whitelist(strategy: str, *pairs: str):
        existing = StrategyTools.metadata().get(strategy, {})
        whitelist = set(existing.get("whitelist", []))
        whitelist.update(pairs)
        existing[strategy] = list(whitelist)

        StrategyTools.save_metadata(existing)

    @staticmethod
    def save_metadata(existing):
        with StrategyTools.metadata_file.open("w") as f:
            yaml.dump(existing, f)

    @staticmethod
    def get_blacklist(strategy):
        if strategy not in StrategyTools.metadata():
            return []
        StrategyTools.metadata()[strategy].get("blacklist", [])

    @staticmethod
    def get_whitelist(strategy):
        if strategy not in StrategyTools.metadata():
            return []
        StrategyTools.metadata()[strategy].get("whitelist", [])

    @staticmethod
    def init_config(config: Config, strategy: str):

        whitelist = StrategyTools.get_whitelist(strategy)
        blacklist = StrategyTools.get_blacklist(strategy)

        temp_path = tempfile.mkdtemp()
        tmp = Path(temp_path, "config.json")
        tmp_config = Config(config.save(save_as=tmp))
        tmp_config.update_whitelist_and_save(whitelist, True)
        tmp_config.update_blacklist(blacklist, True)
        tmp_config.save()
        return tmp_config

    @staticmethod
    def get_file_name(strategy: str) -> str:
        """Returns the file name of a strategy"""
        to_dict = StrategyTools.get_all_strategies()
        return to_dict.get(strategy)

    @staticmethod
    def get_all_strategies():
        if StrategyTools.strategy_dict and StrategyTools._last_strategy_len == len(
            os.listdir(paths.STRATEGY_DIR)
        ):
            return StrategyTools.strategy_dict
        logger.info('Running list-strategies')
        text = sh.freqtrade(
            "list-strategies",
            no_color=True,
            userdir=str(paths.USER_DATA_DIR),
            # _out=lambda l: logger_exec.info(l.strip()),
            # _err=lambda l: logger_exec.info(l.strip()),
        )
        strat_dict = dict(strategy_files_pattern.findall("\n".join(text)))
        StrategyTools.strategy_dict = strat_dict
        StrategyTools._last_strategy_len = len(os.listdir(paths.STRATEGY_DIR))
        return strat_dict

    @staticmethod
    def create_strategy_params_filepath(strategy: str) -> Path:
        """Return the path to the strategies parameter file."""
        logger.debug('Getting parameters path of {}', strategy)
        file_name = StrategyTools.get_file_name(strategy)
        if not file_name:
            raise ValueError("Could not find strategy: %s" % strategy)
        return paths.STRATEGY_DIR.joinpath(file_name.replace(".py", "") + ".json")

    @staticmethod
    def get_name_from_id(id: int) -> str:
        from lazyft.reports import get_hyperopt_repo

        return get_hyperopt_repo().get_by_param_id(id).strategy


if __name__ == "__main__":
    print(StrategyTools.get_file_name('MacheteV8b'))
