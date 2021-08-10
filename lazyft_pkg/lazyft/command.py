from typing import Union

from lazyft.parameters import command_map, CommandParameters, HyperoptParameters
from lazyft.quicktools import QuickTools


class Command:
    def __init__(
        self, strategy, params: Union[CommandParameters, HyperoptParameters], id=None
    ):
        self.strategy = strategy
        self.id = id
        self.config = params.config
        self.params = params
        self.args = ['hyperopt', f'-s {strategy}']

    @property
    def command_string(self):
        params = self.params
        assert (
            params.days or params.timerange
        ), "--days or --timerange must be specified"

        args = self.args.copy()
        if not params.timerange:
            hyperopt_range, backtest_range = QuickTools.get_timerange(
                self.config, params.days, params.interval
            )
            if isinstance(self.params, HyperoptParameters):
                params.timerange = hyperopt_range
            else:
                params.timerange = backtest_range

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
