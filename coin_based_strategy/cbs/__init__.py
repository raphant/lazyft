import json
from pathlib import Path

import rapidjson
from pydantic.dataclasses import dataclass

from lazyft.strategy import StrategyTools
from lazyft import paths
from loguru import logger


@dataclass
class CbsConfiguration:
    map_file: Path


@dataclass(frozen=True)
class Strategy:
    strategy_name: str
    pair: str
    params: dict

    @property
    def joined_name(self):
        return f"{self.strategy_name}-{self.pair.replace('/', '_')}"

    @property
    def tmp_path(self):
        return Path(f"/tmp/{self.joined_name}")

    def create_tmp_dir(self):
        """create a temporary directory for the strategy using the joined name"""
        # mkdir the directory
        self.tmp_path.mkdir(exist_ok=True)

    def copy_params(self):
        file_name = StrategyTools.create_strategy_params_filepath(
            self.strategy_name
        ).name

        # copy the params to the temporary directory as a json file
        path = Path(self.tmp_path, f"{file_name}")
        if not self.params:
            logger.info(f"No params for strategy {self.strategy_name}")
            # delete the file if it exists
            path.unlink(missing_ok=True)
            return
        logger.info(f"writing params to {file_name}")
        path.write_text(rapidjson.dumps(self.params))

    def copy_strategy(self):
        """copy the strategy to the temporary directory"""
        strategy_path = paths.STRATEGY_DIR / self.strategy_file_name
        self.create_tmp_dir()
        Path(self.tmp_path, f"{strategy_path.name}").write_text(
            strategy_path.read_text()
        )

    @property
    def strategy_file_name(self):
        return StrategyTools.get_file_name(self.strategy_name)
