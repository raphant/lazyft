import collections
import pathlib
from typing import Optional

import pandas as pd
import sh
from quicktools.backtest import BacktestReport
from easyft import util, Result, study


class Confirm(study.Study):
    def __init__(
        self, coin: str, results: 'list[Result]', days: Optional[int], **kwargs
    ) -> None:
        super().__init__(coin, [], days=days, **kwargs)
        self.study_results = results
        self.setup_logging()
        self.results: dict[str, list[dict]] = collections.defaultdict(list)

    def run(self) -> None:
        self.running = True

        for result in self.study_results:
            self._current_strategy = result.strategy
            self.debug(
                'Creating strategy %s with id %s'
                % (self._current_strategy.proper_name, result.id)
            )
            result.strategy.create_strategy_with_param_id(self.coin, result.id)
            try:
                self._run(result)
            except sh.ErrorReturnCode_2:
                self.log(self.logs)
                self.log(self.study_results)
            except Exception as e:
                self.log(self.logs)
                # self.logger.exception(e)
                self.log(self.study_results)

            self.current_interval = 0
        self.running = False

    def _run(self, result: Result):
        self.log('Starting backtest %s\n' % result.strategy)
        self.process = sh.manage(
            ['-c', str(self.config_path)],
            'backtest',
            result.strategy.proper_name,
            interval='5m',
            timerange=util.escape_ansi(self.backtest_timerange),
            skip_post_processing=True,
            D=pathlib.Path(result.study_path.parent.name, result.study_path.name),
            _err=lambda log: self.sub_process_log(log, False),
            _out=lambda log: self.sub_process_log(log, False),
        )
        self.extract_output(result)
        self.sub_process_logs.clear()

    def extract_output(self, result: Result):
        # Parse output
        report = BacktestReport.from_output(self.logs)
        dictionary = dict(
            zip(report.df_with_totals.columns, report.df_with_totals.to_numpy()[0])
        )
        dictionary['params_id'] = result.id
        # pprint(df_with_totals)
        self.results[self._current_strategy.strategy_name].append(dictionary)
