import os
from pathlib import Path
from typing import Union
from lazyft.constants import BASE_DIR, CONFIG_DIR
import rapidjson


class Config:
    def __init__(self, config: Union[os.PathLike, str]) -> None:
        temp = Path(config)
        if temp.exists():
            self._config_path = temp.resolve()
        else:
            self._config_path = Path(CONFIG_DIR, config).resolve()
            assert self._config_path.exists(), f'"{self._config_path}" doesn\'t exist'
        self._data: dict = rapidjson.loads(self._config_path.read_text())

    def send_ssh(self, bot_id: str):
        # todo send config to a bot via ssh
        pass

    def save(self, save_as: Union[os.PathLike, str] = None) -> Path:
        if not save_as:
            self._config_path.write_text(self.to_json)
            path = self._config_path
        else:
            if isinstance(save_as, str):
                path = self._config_path.parent.joinpath(save_as)
                path.write_text(self.to_json)
            else:
                path = Path(save_as).write_text(self.to_json)
        self._config_path = path
        return path

    @property
    def to_json(self) -> str:
        return rapidjson.dumps(self._data, indent=2)

    @property
    def data(self):
        return self._data.copy()

    @property
    def path(self):
        return self._config_path

    @classmethod
    def new(cls, config_name: str, from_config: Union[str, 'Config']):
        return cls(cls(str(from_config)).save(config_name))

    def get(self, key, default=None):
        return self._data.get(key, default)

    def copy(self):
        return self._data.copy()

    def __getitem__(self, key: str):
        return self._data[key]

    def __setitem__(self, key: str, item: object):
        self._data[key] = item

    def __str__(self) -> str:
        return str(self.path)

    def __repr__(self) -> str:
        return str(self.path)


if __name__ == '__main__':
    c = Config('/home/raphael/PycharmProjects/freqtrade/config1.json')
    c['max_open_trades'] = 500
    new_path = c.save('config1.json')
    print(c.data)
    print(new_path)
