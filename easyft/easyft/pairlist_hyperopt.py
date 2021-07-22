import pathlib
from typing import Optional, Iterable

import loguru
from easyft import study, hyperopt, constants
from easyft.strategy import Strategy
from easyft.config import Config
from rich.logging import RichHandler


class Hyperopt(hyperopt.Hyperopt):
    _current_strategy: Strategy
    strategies: Iterable[Strategy]

    def __init__(
        self,
        strategies: Iterable[Strategy],
        config_path: pathlib.Path,
        intervals: Optional[int],
        epochs: Optional[int],
        min_trades: Optional[int],
        spaces: Optional[list],
        days: int,
        loss_function: str,
        pairlist: str = None,
        refresh_pairlist=False,
        **kwargs,
    ) -> None:
        super().__init__(
            None,
            strategies,
            intervals,
            epochs,
            min_trades,
            spaces,
            days,
            loss_function,
            config_path=config_path,
            skip_download_data=True,
            **kwargs,
        )
        self.max_intervals = intervals
        self.epochs = epochs
        self.process = None
        self.running = False
        self.min_trades = min_trades
        self.run_logs: list[str] = []
        self.results: list[study.Result] = []
        self.spaces = spaces
        self.current_interval = 0
        self.final = {}
        self.loss_function = loss_function

        if refresh_pairlist:
            # todo create temp config file with new pairs
            pass
        elif pairlist:
            # todo change whilelist to pairs from passed pairlist
            pass
        self.config = Config(config_path)
        # todo download data from timeframe/days

    def _run(self, strategy: Strategy):
        self.log('Hyperopting strategy %s\n' % strategy)
        while self.current_interval < self.max_intervals:
            self.log(
                'Starting interval #%s of %s'
                % (self.current_interval + 1, self.max_intervals)
            )
            if not strategy.id:
                strategy_path = study.StudyManager.TEMPLATE_DIR
            else:
                strategy_path = strategy.create_strategy()
                # self.log(str(strategy_path) + '\n')
            self._start_hyperopt(strategy, strategy_path)
            self.extract_output()
            self.sub_process_logs.clear()
            self.current_interval += 1

    @property
    def study_path(self):
        path = constants.STUDY_DIR.joinpath(self._current_strategy)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def setup_logging(self):
        constants.BASE_DIR.joinpath('study_logs').mkdir(exist_ok=True)

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
                    sink=constants.BASE_DIR.joinpath(
                        'study_logs', f'{self._current_strategy}.log'
                    ),
                    backtrace=True,
                    diagnose=True,
                    level='DEBUG',
                    delay=True,
                ),
            ]
        )
        self.logger = loguru.logger
