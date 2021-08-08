import rapidjson

from lazyft import paths, logger


class Pairlist:
    @staticmethod
    def load_from_id(strategy: str, id: str):
        logger.debug('loading pairlist from id {} for strategy {}', strategy, id)
        if not paths.PARAMS_FILE.exists():
            raise FileNotFoundError('Params file does not exist.')
        # load params as json
        params_dict = rapidjson.loads(paths.PARAMS_FILE.read_text())
        if strategy not in params_dict:
            raise KeyError('Strategy %s not found in params file' % strategy)
        params_strategy = params_dict[strategy]
        if id not in params_strategy:
            raise KeyError('Id %s not found for strategy' % id)
        if 'pairlist' not in params_strategy[id]:
            raise KeyError(
                'Pairlist not found in strategy %s for id %s' % (strategy, id)
            )
        return params_strategy[id]['pairlist']
