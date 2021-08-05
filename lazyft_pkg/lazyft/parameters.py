from collections import UserDict
from pprint import pprint

import pandas as pd
import rapidjson
from dateutil.parser import parse

from lazyft import logger
from lazyft.constants import ID_TO_LOAD_FILE, PARAMS_FILE
from lazyft.pairlist import Pairlist


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


class Parameter(UserDict):
    def __init__(self):
        data = rapidjson.loads(PARAMS_FILE.read_text())
        super().__init__(data)

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

        columns = list(performances[0].keys())
        df = pd.DataFrame(performances, columns=columns)
        return df

    def get_params(self, strategy: str, id: str):
        try:
            return self[strategy][id]['params']
        except KeyError:
            raise KeyError('Could not load params for %s-%s', strategy, id)

    @staticmethod
    def get_pairlist(strategy: str, id: str) -> list[str]:
        return Pairlist.load_from_id(strategy, id)


if __name__ == '__main__':
    print(Parameter().get_performances('BollingerBands2').to_string())
    print('fCOoUY:')
    pprint(Parameter().get_params('BollingerBands2', 'fCOoUY'))
    print('c32vVv:')
    pprint(Parameter().get_params('BollingerBands2', 'c32vVv'))
    p1 = Parameter.get_pairlist('BollingerBands2', 'fCOoUY')
    p2 = Parameter.get_pairlist('BollingerBands2', 'c32vVv')
