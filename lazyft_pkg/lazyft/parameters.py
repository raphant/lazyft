from typing import TYPE_CHECKING

import rapidjson
import yaml
from lazyft import util, logger
from lazyft.constants import BASE_DIR, ID_TO_LOAD_FILE
from box import Box

if TYPE_CHECKING:
    from .hyperopt import HyperoptPerformance


class Parameters:
    SAVE_PATH = BASE_DIR.joinpath('lazy_params.json')

    def __init__(
        self,
        params: dict,
        performance: 'HyperoptPerformance',
        strategy: str,
    ) -> None:
        self.id = util.rand_token()
        self.params = params
        self.strategy = strategy
        self.performance = performance

    @property
    def path(self):
        return


class ParamsToLoad:
    @classmethod
    def set_id(cls, strategy: str, id: str):
        logger.info(
            'Updating params_to_load strategy "%s" to load param ID "%s"',
            strategy,
            id,
        )
        if not ID_TO_LOAD_FILE.exists():
            data = {}
        else:
            data = rapidjson.loads(ID_TO_LOAD_FILE.read_text())
        data[strategy] = id
        ID_TO_LOAD_FILE.write_text(rapidjson.dumps(data))


if __name__ == '__main__':
    ParamsToLoad.set_id('strat', '555')
