import collections
import json
import logging
import pathlib
import shutil
import threading
import uuid
from abc import ABCMeta, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

import attr
import loguru
import sh
from easyft import util, constants, print
from easyft.strategy import StudyParams
from rich.logging import RichHandler

if TYPE_CHECKING:
    from easyft import SingleCoinStrategy, Performance, AbstractStrategy


class Study(threading.Thread, metaclass=ABCMeta):
    def __init__(
        self,
        coin: Optional[str],
        strategies: list['AbstractStrategy'],
        days: int,
        config_path: pathlib.Path = None,
        verbose=False,
        skip_download_data=False,
    ) -> None:
        super().__init__()
        self._logs: list[str] = []
        self.sub_process_logs: list[str] = []
        self.coin = coin
        self.config_path = config_path
        self.strategies = strategies
        self.logger: logging.Logger = loguru.logger
        self._status = None
        self.process = None
        self.running = False
        self.id = str(uuid.uuid4())
        self.run_logs: list[str] = []
        self.results: list[Result] = []
        self.current_interval = 0
        self._current_strategy = ''
        self.final = {}
        self.days = days
        self.verbose = verbose
        self.skip_download_data = skip_download_data
        self.params = StudyParams(coin)
        if not config_path:
            config_path = pathlib.Path(
                constants.BASE_DIR, f'study_config-{coin.split("/")[0]}.json'
            ).resolve()
        self.config_path = config_path
        shutil.copy(constants.BASE_CONFIG_PATH, config_path)
        util.set_pairlist(coin, config_path)
        if not skip_download_data:
            self.log('Downloading %s days of market data for %s\n' % (days, coin))
            sh.freqtrade(
                'download-data',
                days=days,
                c=self.config_path,
                userdir=constants.FT_DATA_DIR,
                _err=lambda log: self.sub_process_log(log, False),
            )

        timerange = sh.manage(
            ['-c', str(self.config_path), 'get-ranges', '5m', '-c', '-d', str(days)],
            _err=self.sub_process_logs,
        )
        self.hyperopt_timerange, self.backtest_timerange = str(timerange).split(',')

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def _run(self, strategy: 'SingleCoinStrategy'):
        pass

    @abstractmethod
    def extract_output(self, args):
        pass

    def sub_process_log(self, text='', out=False):
        if not text or 'ETA' in text:
            return
        text = text.strip()
        self.sub_process_logs.append(text)
        self.logger.debug(text)
        if out or self.verbose:
            print(text, end='\n')

    def debug(self, text=''):
        text = str(text)

        if self.verbose:
            return self.log(text)
        try:
            self.logger.debug(text.strip())
        except AttributeError:
            self.logger.debug(text)

    def log(self, text: Any = ''):
        text = str(text)

        try:
            self.logger.debug(text.strip())
        except AttributeError:
            self.logger.debug(text)
        print(text)

    def setup_logging(self):
        StudyManager.BASE_DIR.joinpath('study_logs').mkdir(exist_ok=True)

        loguru.logger.configure(
            handlers=[
                dict(
                    sink=RichHandler(),
                    level='INFO',
                    backtrace=False,
                    diagnose=False,
                    enqueue=True,
                ),
                dict(
                    sink=StudyManager.BASE_DIR.joinpath(
                        'study_logs', f'{self.coin.replace("/", "-")}.log'
                    ),
                    backtrace=True,
                    diagnose=True,
                    level='DEBUG',
                    delay=True,
                ),
            ]
        )
        self.logger = loguru.logger

    @property
    def study_path(self):
        joinpath = StudyManager.STUDY_DIR.joinpath(self.coin.replace('/', '_'))
        joinpath.mkdir(parents=True, exist_ok=True)
        return joinpath

    @property
    def logs(self):
        return '\n'.join(self.sub_process_logs)


class StudyManager:
    BASE_DIR = pathlib.Path(constants.SCRIPT_DIRECTORY, '../../').resolve()
    FT_DATA_DIR = pathlib.Path(BASE_DIR, 'user_data').resolve()
    STUDY_DIR = pathlib.Path(FT_DATA_DIR, 'strategies', 'study').resolve()
    TEMPLATE_DIR = pathlib.Path(STUDY_DIR, 'templates').resolve()

    def __init__(
        self, base_config_name: str = 'study_config.json', strategies=None
    ) -> None:
        super().__init__()
        self.config_path = pathlib.Path(self.BASE_DIR, base_config_name)
        self.strategies = strategies or []

        assert self.config_path.exists(), (
            str(self.config_path.absolute()) + ' does not exist'
        )

    def new_hyperopt(
        self,
        coin: str,
        strategies: list['SingleCoinStrategy'] = None,
        intervals=75,
        epochs=100,
        min_trades=100,
        days=30,
        spaces=None,
        loss_function=None,
        verbose: bool = False,
    ):
        from easyft import hyperopt

        hyperopt = hyperopt.Hyperopt(
            coin,
            strategies or self.strategies,
            intervals,
            epochs,
            min_trades=min_trades,
            spaces=spaces,
            days=days,
            verbose=verbose,
            loss_function=loss_function,
        )
        hyperopt.setup_logging()
        return hyperopt


@attr.s
class Result:
    strategy: 'SingleCoinStrategy' = attr.ib()
    params: dict = attr.ib()
    study_path: pathlib.Path = attr.ib()
    id = attr.ib(default='', converter=util.rand_token)
    performance: Optional['Performance'] = attr.ib(default=None)

    @property
    def params_path(self):
        return self.study_path.joinpath('params.json')

    def save(self):
        if not self.params_path.exists():
            self.params_path.write_text('{}')

        file_params = json.loads(self.params_path.read_text())
        # get the strategy section or create one
        strategy_section: dict = file_params.get(self.strategy.proper_name, {})
        # create the id key and set it to the parameters
        id_section: dict = strategy_section.get(self.id, collections.defaultdict(dict))
        id_section['performance'].update(self.performance.__dict__)
        id_section['params'].update(self.params)
        strategy_section[self.id] = id_section

        # assign the section back to params
        file_params[self.strategy.proper_name] = strategy_section
        self.params_path.write_text(json.dumps(file_params, indent=2))
        return self.id

    @classmethod
    def from_params(
        cls, strategy: 'SingleCoinStrategy', id_: str, study_path: pathlib.Path
    ):
        params = json.loads(study_path.joinpath('params.json').read_text())[
            strategy.proper_name
        ][id_]
        return cls(strategy, params, study_path, id=id_)
