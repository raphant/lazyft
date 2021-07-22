import os
from pathlib import Path
from typing import Union

import rapidjson


class Config:
    def __init__(self, config: Union[os.PathLike, str]) -> None:
        temp = Path(config)
        if temp.exists():
            self._config_path = temp.resolve()
        else:
            self._config_path = Path('../../../', config).resolve()
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

        return path

    @property
    def to_json(self) -> str:
        return rapidjson.dumps(self._data, indent=2)

    @property
    def data(self):
        return self._data

    @property
    def path(self):
        return self._config_path

    def get(self, key, default=None):
        return self._data.get(key, default)

    def copy(self):
        return self._data.copy()

    def __getitem__(self, key: str):
        return self._data[key]

    def __setitem__(self, key: str, item: object):
        self._data[key] = item


if __name__ == '__main__':
    c = Config('/home/raphael/PycharmProjects/freqtrade/config1.json')
    c['max_open_trades'] = 500
    new_path = c.save('config1.json')
    print(c.data)
    print(new_path)
