import rapidjson

from lazyft import logger
from lazyft.constants import ID_TO_LOAD_FILE


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
