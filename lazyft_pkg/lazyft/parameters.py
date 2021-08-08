from collections import UserDict
from pathlib import Path

import pandas as pd
import rapidjson
from dateutil.parser import parse

from lazyft.paths import (
    PARAMS_FILE,
    BACKTEST_RESULTS_FILE,
    STRATEGY_DIR,
    PARAMS_DIR,
)
from lazyft.strategy import Strategy

cols = [
    'id',
    'starting_balance',
    'stake_amount',
    'max_open_trades',
    'trades',
    'wins',
    'losses',
    'draws',
    'avg_profits',
    'med_profit',
    'tot_profit',
    'profit_percent',
    'avg_duration',
    'loss',
    'seed',
    'from_date',
    'days',
]


class Parameter:
    @classmethod
    def set_params_file(cls, strategy: str, id: str):
        """Load strategy parameters from a saved param export."""
        id_param_file = cls.get_path_of_params(id)
        if not id_param_file.exists():
            raise FileNotFoundError('Could not find parameters for id "%s"' % id)
        # get full name that the params file will be saved as
        strategy_json = Strategy.create_strategy_params_filepath(strategy)
        # setup the file path
        new_params_file = STRATEGY_DIR.joinpath(strategy_json)
        # write into the new params file
        new_params_file.write_text(id_param_file.read_text())

    @classmethod
    def get_path_of_params(cls, id):
        """Returns the path to the params file in the saved_params directory using the id"""
        id_param_file = PARAMS_DIR.joinpath(id + '.json')
        return id_param_file

    @classmethod
    def reset_id(cls, strategy):
        Strategy.create_strategy_params_filepath(strategy).unlink(missing_ok=True)

    @classmethod
    def load_data(cls):
        if not PARAMS_FILE.exists():
            data = {}
        else:
            data = rapidjson.loads(PARAMS_FILE.read_text())
        return data


class ResultBrowser(UserDict):
    def __init__(self):
        data = rapidjson.loads(PARAMS_FILE.read_text())
        super().__init__(data)

    @property
    def backtest_data(self):
        return rapidjson.loads(BACKTEST_RESULTS_FILE.read_text())

    def get_performances(self, strategy: str) -> pd.DataFrame:
        performances = []
        assert strategy in self, "Strategy doesn't exist"
        for id, id_dict in self[strategy].items():
            perf = {'id': id}
            perf.update(id_dict.get('balance_info', {}))
            perf.update(id_dict['performance'])
            perf['days'] = abs(parse(perf['from_date']) - parse(perf['to_date'])).days
            perf.pop('to_date')
            performances.append(perf)

        df = pd.DataFrame(performances)
        return df

    def get_params(self, strategy: str, id: str):
        try:
            return rapidjson.loads(Path(self[strategy][id]['params_file']).read_text())
        except KeyError:
            raise KeyError('Could not load params for %s-%s' % (strategy, id))

    def get_backtest_results(self, strategy: str):
        if strategy not in self.backtest_data:
            raise KeyError(
                'Strategy "%s" not found in %s' % (strategy, BACKTEST_RESULTS_FILE.name)
            )
        performances = []
        for p in self.backtest_data[strategy]:
            data = {'id': p.get('id')}
            data.update(p['performance'])
            data.update(
                {
                    'start_date': p.get('start_date'),
                    'end_date': p.get('end_date'),
                }
            )
            performances.append(data)
        df = pd.DataFrame(performances)
        return df

    def get_backtest_result_from_id(self, strategy: str, id: str):
        if strategy not in self.backtest_data or id not in [strategy]:
            raise KeyError(
                'Strategy "%s" or id "%s" not found in %s'
                % (strategy, id, BACKTEST_RESULTS_FILE.name)
            )
        data = [self.backtest_data[strategy][id]['performance']]
        return pd.DataFrame(data)


if __name__ == '__main__':
    print(ResultBrowser().get_backtest_results('TestBinH').to_string())
    # print('Ln70qa:')
    # pprint(ResultBrowser().get_params('BollingerBands2', 'Ln70qa'))
    # print('c32vVv:')
    # pprint(ResultBrowser().get_params('BollingerBands2', 'c32vVv'))
