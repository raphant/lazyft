from collections import defaultdict

import rapidjson
from freqtrade.data.dataprovider import DataProvider
from loguru import logger
from cbs import CbsConfiguration, Strategy


class Mapper:
    def __init__(self, config: CbsConfiguration):
        self.config = config
        self.maps = self.load()
        logger.info(f'Loaded {len(self.maps)} pairs')

    def load(self) -> dict[str, list]:
        logger.info(f'Loading {self.config.map_file}')
        return defaultdict(list, rapidjson.loads(self.config.map_file.read_text()))

    def get_strategies(self, pair: str) -> list[Strategy]:
        if pair not in self.maps:
            return []
        strategies = self.maps[pair]
        logger.debug(f'Found {len(strategies)} strategies for {pair}')
        return [Strategy(**i, pair=pair) for i in strategies]

    def get_maps(self):
        return self.maps

    def map(self, pair, strategy_name, params: dict = None):
        if not params:
            params = {}
        for idx, k in enumerate(self.maps[pair]):
            if strategy_name in k['strategy_name']:
                self.maps[pair][idx]['params'].update(params)
                logger.info(f'Updated strategy {strategy_name} for {pair}')
                break
        else:
            self.maps[pair].append({'strategy_name': strategy_name, 'params': params})
            logger.info(f'Mapped {strategy_name} to {pair}')

    def save(self):
        self.config.map_file.write_text(rapidjson.dumps(self.maps))
        logger.info(f'Saved {len(self.maps)} pairs')

    def delete_pair(self, *pair: str):
        for p in pair:
            if p in self.maps:
                del self.maps[p]
                logger.info(f'Deleted {p}')
