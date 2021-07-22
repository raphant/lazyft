import json
import pathlib
import uuid
from abc import ABCMeta, abstractmethod
from collections import Iterable


from lazyft import constants, util


class AbstractStrategy(metaclass=ABCMeta):
    TEMPLATE_DIR = pathlib.Path(constants.STUDY_DIR, 'templates')

    def __init__(self, strategy_name: str, id: str, save_dir=constants.STUDY_DIR):
        self.id = id
        self.strategy_name = strategy_name
        self.save_dir = save_dir

    @property
    def proper_name(self):
        return (
            f'Study{self.strategy_name}'
            if 'Study' not in self.strategy_name
            else self.strategy_name
        )

    def __str__(self):
        return self.proper_name

    def __repr__(self):
        return f'Strategy(strategy={self.proper_name}, id={self.id})'

    @property
    def base_strategy_path(self):
        return self.TEMPLATE_DIR.joinpath(f'{self.strategy_name.lower()}.py')

    @abstractmethod
    def create_strategy_with_param_id(self, *args, **kwargs) -> pathlib.Path:
        """
        Returns the path of the new strategy file
        """
        pass

    @abstractmethod
    def create_strategy(self, *args, **kwargs) -> pathlib.Path:
        """
        Returns the path of the new strategy file
        """
        pass


class SingleCoinStrategy(AbstractStrategy):
    def __init__(self, strategy_name: str, id: str = None, coin=None, **kwargs) -> None:
        super().__init__(strategy_name, id, **kwargs)
        self.coin = coin
        if id:
            self._new_id = self.create_id(id, coin)

    @property
    def new_id(self):
        self._new_id = self._new_id or self.create_id(self._new_id, self.coin)
        return self._new_id

    def create_strategy_with_param_id(self, coin: str, id_: str):
        python_text = self.base_strategy_path.read_text()
        python_text = python_text.replace('$NAME', id_)
        new_strategy_path = self.save_dir.joinpath(
            coin.replace('/', '_'), f'{self.strategy_name.lower()}.py'
        )
        try:
            with new_strategy_path.open('w') as f:
                f.write(python_text)
        except FileNotFoundError:
            raise FileNotFoundError(f'No existing folder for coin "{coin}"')

        return new_strategy_path

    def create_id(self, id: str, coin=None):
        """Auto-increment ID if an existing ID is passed"""
        params = {}
        if coin:
            params = SingleCoinStudyParams(coin).dict
        # find all existing IDs that match id param
        existing_ids = [k for k in params[self.proper_name] if id.split('-')[0] in k]
        return f'{id}-{len(existing_ids) + 1}'
        # if '-' in id:
        #     base_id, num = id.split('-')
        #     num = int(num)
        #     return f'{base_id}-{num+1}'
        # else:
        #     return f'{id}-1'

    def create_strategy(self, coin):
        return self.create_strategy_with_param_id(coin, self.id).parent

    @classmethod
    def create_strategies(cls, strategies: Iterable[str], coin: str):
        formatted_strategies = []
        print(strategies)

        for s in strategies:
            id = None
            strategy = s
            if '-' in s:
                strategy, id = s.split('-')
            formatted_strategies.append(SingleCoinStrategy(strategy, id=id, coin=coin))
        return formatted_strategies


class Strategy(AbstractStrategy):
    def __init__(self, strategy_name: str, id: str, **kwargs) -> None:
        super().__init__(strategy_name, id, **kwargs)
        self.id = id
        if id:
            self._new_id = self.create_id(id)
            self.create_strategy()

    @property
    def new_id(self):
        self._new_id = self._new_id or self.create_id(self._new_id)
        return self._new_id

    @property
    def path_to_delete(self):
        return self.path.parent.joinpath(self.strategy_name.lower() + '.json')

    @property
    def path(self):
        if not self.id:
            return constants.TEMPLATE_DIR.joinpath(self.proper_name + '.py')
        new_strategy_path = self.save_dir.joinpath(
            self.proper_name, f'{self.strategy_name.lower()}.py'
        )
        return new_strategy_path

    def create_id(self, id: str):
        params = {}
        study_params = StudyParams(self.proper_name)
        if study_params.path.exists():
            params = study_params.dict
        existing_ids = [k for k in params if id.split('-')[0] in k]
        return f'{id}-{len(existing_ids) + 1}'

    def create_strategy_with_param_id(self, id_: str):
        python_text = self.base_strategy_path.read_text()
        python_text = python_text.replace('$NAME', id_)
        new_strategy_path = self.path
        new_strategy_path.parent.mkdir(exist_ok=True)
        try:
            with new_strategy_path.open('w') as f:
                f.write(python_text)
        except FileNotFoundError:
            raise FileNotFoundError(
                f'No existing folder for strategy "{self.proper_name}"'
            )
        return new_strategy_path

    def create_strategy(self):
        if not self.id:
            return constants.TEMPLATE_DIR.joinpath(self.proper_name + '.py')
        return self.create_strategy_with_param_id(self.id)

    @classmethod
    def create_strategies(cls, *strategies: str):
        formatted_strategies = []

        for s in strategies:
            id = None
            strategy = s
            if '-' in s:
                strategy, id = s.split('-')
            formatted_strategies.append((strategy, id))
        return [cls(s, id) for s, id in formatted_strategies]


class SingleCoinStudyParams:
    def __init__(self, coin: str) -> None:
        self.coin = coin

    @property
    def dict(self) -> dict:
        return json.loads(self.path.read_text())

    @property
    def path(self):
        return pathlib.Path(
            constants.STUDY_DIR.joinpath(self.coin.replace('/', '_'), 'params.json')
        )

    def mkdir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)


class StudyParams:
    def __init__(self, strategy: str) -> None:
        self.strategy = strategy

    @property
    def dict(self) -> dict:
        breakpoint()
        return json.loads(self.path.read_text())

    @property
    def path(self):
        return pathlib.Path(constants.STUDY_DIR.joinpath(self.strategy, 'params.json'))

    def mkdir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
