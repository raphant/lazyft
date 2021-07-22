from pathlib import Path

import quicktools
import rich.console
import typer
from quicktools.hyperopt import QuickHyperopt
from quicktools.quick_tools import QuickTools

cli = typer.Typer()

print = rich.console.Console().print


@cli.command()
def backtest():
    pass


@cli.command()
def hyperopt(
    ctx: typer.Context,
    strategy: str = typer.Argument(...),
    spaces: str = typer.Argument(
        ...,
        help='Example: For \'roi, buy, & sell\': "rbs". Options:\n'
        + QuickHyperopt.spaces_help,
    ),
    directory: str = typer.Option(
        None, '-D', '--directory', help='The directory for the strategy.'
    ),
    days: int = typer.Option(
        90,
        '-d',
        '--days',
        help='This will get the first 2/3rds of the days specified and convert it to a '
        'timerange. Similarly, backtest will use the last 1/3rd. '
        'This will only be used when --days is not provided',
    ),
    timerange: str = typer.Option(None, '-t', '--timerange'),
    interval: str = typer.Option(quicktools.DEFAULT_TICKER, '-i', '--interval'),
    config_path: Path = typer.Option(
        ..., '-c', '--config', resolve_path=True, exists=True
    ),
    loss_function: int = typer.Option(0, '-l', '--loss-function'),
    epochs: int = typer.Option(
        500,
        '-e',
        '--epochs',
    ),
    epoch_intervals: int = typer.Option(
        1,
        '-E',
        '--epoch-intervals',
        help='The total number of epochs will be split this many intervals.'
        ' Fish terminal only',
    ),
    min_trades=typer.Option(100, '-m', '--min-trades'),
    pairs_name: str = typer.Option('', '-p', '--pairs-name'),
    extra_args: str = typer.Option(
        '',
        '--args',
        help='Additional args to add that are not covered here. Example: --args \'-j 3\'',
    ),
):
    """
    Return a hyperopt cli command to run
    """
    # parse spaces
    spaces = QuickHyperopt.get_spaces(spaces)
    # parse days
    if not timerange:
        timerange = QuickTools.get_timerange(days, interval)
    if pairs_name:
        QuickTools.change_pairs(config_path, pairs_name)
    # create command

    args_list = []
    if epoch_intervals > 1:
        args_list.append(f'for i in (seq 1 {int(epoch_intervals)});')

    args_list.append(f'freqtrade hyperopt')
    args_list.append(f'-s {strategy}')
    args_list.append(f'--timerange {timerange} --spaces {spaces}')
    args_list.append(f'-e {int(epochs / epoch_intervals)}')
    args_list.append(f'--min-trades {min_trades}')
    args_list.append(f'-i {interval}')

    args_list.append(extra_args)
    args_list.append(f" -c {config_path or ctx.obj['config_path']}")
    if not loss_function == 5:
        args_list.append(
            f' --hyperopt-loss {QuickHyperopt.loss_func_dict[str(loss_function)]}'
        )
    if directory:
        args_list.append(f" --strategy-path user_data/strategies/{directory}")
    if epoch_intervals > 1:
        args_list.append(';end')
    print(' '.join(args_list))


if __name__ == '__main__':
    cli()
