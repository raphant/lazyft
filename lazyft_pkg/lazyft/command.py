from typing import Union

from lazyft.command_parameters import (
    command_map,
    BacktestParameters,
    HyperoptParameters,
)
from lazyft.quicktools import QuickTools
from lazyft import downloader


class Command:
    def __init__(
        self, strategy, params: Union[BacktestParameters, HyperoptParameters], id=None
    ):
        self.strategy = strategy
        self.hyperopt_id = id
        self.config = params.config
        self.params = params
        self.args = ['hyperopt', f'-s {strategy}']
        self.pairs = None
        if params.download_data:
            downloader.download_missing_historical_data(self.config, params)

    @property
    def command_string(self):
        params = self.params
        args = self.args.copy()

        for key, value in params.__dict__.items():
            if not value or key not in command_map or key == 'days':
                continue
            if value is True:
                value = ''
            if key == 'pairs':
                value = ' '.join(value)
            arg_line = f"{command_map[key]} {value}".strip()
            args.append(arg_line)
        return ' '.join(args)

    def download_data(self):
        QuickTools.download_data(
            config=self.params.config,
            pairs=self.pairs,
            interval=self.params.intervals_to_download,
            days=self.params.days,
            timerange=self.params.timerange,
            secrets_config=self.params.secrets_config,
        )
