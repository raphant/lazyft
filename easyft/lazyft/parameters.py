from typing import TYPE_CHECKING

import yaml
from lazyft import util, strategy
from lazyft.constants import BASE_DIR

if TYPE_CHECKING:
    from .hyperopt import HyperoptPerformance


class Parameters:
    SAVE_PATH = BASE_DIR.joinpath('lazy_params.yaml')

    def __init__(
        self,
        params: dict,
        performance: 'HyperoptPerformance',
        strategy: strategy.Strategy,
    ) -> None:
        self.id = util.rand_token()
        self.params = params
        self.strategy = strategy
        self.performance = performance

    def save(self):
        data = self.add_to_existing_data()
        with self.SAVE_PATH.open('w') as f:
            yaml.dump(data, f)
        # self.SAVE_PATH.write_text(rapidjson.dumps(data))

    def add_to_existing_data(self):
        # grab all data
        data = self.get_existing_data()
        # get strategy data if available, else create empty dict
        strategy_data = data.get(self.strategy.strategy_name, {})
        # add the current params to id in strategy data
        strategy_data[self.id] = {
            'params': self.params,
            'performance': self.performance.__dict__,
        }
        # add strategy back to all data
        data[self.strategy.strategy_name] = strategy_data
        return data

    @classmethod
    def get_existing_data(cls):
        if cls.SAVE_PATH.exists():
            with cls.SAVE_PATH.open('r') as f:
                return yaml.load(f)
            # return rapidjson.loads(self.SAVE_PATH.read_text())
        return {}

    @property
    def path(self):
        return

    @classmethod
    def from_id(cls, strategy_name: str, id: str):
        return cls.get_existing_data()[strategy_name][id]
