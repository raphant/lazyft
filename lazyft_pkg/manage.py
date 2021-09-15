import fnmatch
import json
import os
import shutil
import sys
from datetime import datetime
from numbers import Number
from pathlib import Path
from pprint import pprint
from string import Template, Formatter

import click
import pandas as pd
import rapidjson
import requests
import sh
from arrow import Arrow, now
from bullet import Bullet
from dotenv import load_dotenv
from halo import Halo
from quicktools.backtest import BacktestOutputExtractor
from quicktools.quick_tools import PairListTools

from lazyft import logger

# region Config
os.chdir('../../')

logger.configure(
    handlers=[
        dict(sink=sys.stderr, level='INFO', backtrace=False, diagnose=False),
        dict(sink="manage.log", backtrace=True, diagnose=True, level='DEBUG'),
    ]
)
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 2000)
pd.set_option('display.width', 150)
pd.set_option('precision', 8)

load_dotenv('.environment')
spinner = Halo(text='Working', spinner='dots')

DATA_COLUMNS = ['open_time', 'open', 'high', 'low', 'close', 'volume']
DATE_FORMAT = 'YYYYMMDD'

spaces_dict = {
    'a': 'all',
    'b': 'buy',
    's': 'sell',
    'S': 'stoploss',
    't': 'trailing',
    'r': 'roi',
}
loss_func_dict = {
    '0': 'SortinoHyperOptLossDaily',
    '1': 'SortinoHyperOptLoss',
    '2': 'SharpeHyperOptLossDaily',
    '3': 'SharpeHyperOptLossDaily',
    '4': 'OnlyProfitHyperOptLoss',
    '5': 'ShortTradeDurHyperOptLoss',
}
losses_help = '\n'.join([f'{k}:{v}' for k, v in loss_func_dict.items()])
spaces_help = '\n'.join([f'{k}:{v}' for k, v in spaces_dict.items()])
pair_names_json = 'pair-names.json'


# endregion

# region helper functions
def load_config(ctx) -> dict:
    path = ctx.get('config_path')
    with open(path, 'r') as f:
        return json.load(f)


def save_backtest_results(pairs_name, results):
    dt = now().format('YYYYMMDDHHmmss')
    data_dir = Path('user_data/backtests/')
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = data_dir.joinpath('logs/')
    logs_dir.mkdir(exist_ok=True)
    logfile = logs_dir.joinpath(''.join((dt, '-', pairs_name + '.log')))
    result_file = data_dir.joinpath('backtest-results.json')
    if not result_file.exists():
        result_file.touch()
        existing_data = {}
    else:
        existing_data = rapidjson.loads(result_file.read_text())
    existing_data[dt] = {
        'pairs_name': pairs_name,
        'logfile': str(logfile.resolve()),
        'result': results.df.trades_to_csv(index=False).splitlines(),
        'winners': list(results.winners['Pair'].values),
    }
    result_file.write_text(rapidjson.dumps(existing_data))
    return logfile


def get_timerange(days, interval, backtesting=False):
    lines = []

    def parse_output(string):
        lines.append(string)

    sh.python(
        ['manage', 'get-ranges', interval, '-d', str(days), '-c'],
        _out=parse_output,
        _err=print,
    )
    return lines[0][:35].split(',')[1 if backtesting else 0]


def save_config(config: dict, ctx: dict):
    path = ctx.get('config_path')
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)


def get_config_value(config: dict, value: str):
    values = value.split('.')
    trail = config.copy()

    for value in values:
        trail = trail[value]

    return trail


def convert_price(convert_to: str, amount: Number, convert_from='USDC'):
    params = {"amount": amount, "symbol": convert_from, "convert": convert_to}
    headers = {
        "X-CMC_PRO_API_KEY": os.getenv('COINBASE_API_KEY'),
        "Accept": "application/json",
    }
    api_url = 'https://pro-api.coinmarketcap.com'
    response = requests.get(
        f'{api_url}/v1/tools/price-conversion', params=params, headers=headers
    )
    try:
        response.raise_for_status()
    except Exception as e:
        logger.exception(e)
        exit(-1)
    logger.debug(response.json())
    return response.json()['data']['quote'][convert_to]['price']


def find(pattern, path):
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(os.path.join(root, name))
    return result


def create_dataframe(pairs: list):
    def get_sec(time_str):
        """Get Seconds from time."""
        try:
            h, m, s = time_str.split(':')
        except ValueError:
            return '0:0:0'
        return int(h) * 3600 + int(m) * 60 + int(s)

    df = pd.DataFrame(
        pairs,
        columns=[
            'Pair',
            'Buys',
            'Average Profit',
            'Accumulative Profit',
            'Total Profit USD',
            'Total Profit %',
            'Average Duration',
            'Wins',
            'Draws',
            'Losses',
        ],
    )
    df["Average Duration"] = df["Average Duration"].apply(get_sec)
    for c in df:
        df[c] = pd.to_numeric(df[c], errors='ignore')
    return df


def get_best_result(n=-1):
    output = []

    def printf(string: str):
        if 'freqtrade' not in string:
            output.append(string)

    sh.freqtrade(
        'hyperopt-show',
        best=True,
        n=n,
        print_json=True,
        no_header=True,
        _out=printf,
        _err=printf,
    )
    return output.pop().strip()


def change_pairs(ctx, pairs_name):
    config = load_config(ctx.obj)
    pairlist_names = rapidjson.loads(Path(pair_names_json).read_text())
    try:
        pairlist = pairlist_names[pairs_name]
    except KeyError:
        click.echo(f'\nCould not find pairlist: "{pairs_name}"')
        return exit(1)
    config['exchange']['pair_whitelist'] = pairlist['list']
    save_config(config, ctx.obj)


# endregion

# region core
@click.group()
@click.option(
    '-c',
    '--config-path',
    default='config.json',
    type=click.Path(exists=True),
    show_default=True,
)
@click.option('-o', '--output-path', help='Save to a new config file')
@click.pass_context
def core(ctx, config_path: str, output_path: str):
    ctx.ensure_object(dict)
    if output_path:
        shutil.copyfile(config_path, output_path)
        config_path = output_path
    ctx.obj['config_path'] = config_path


# endregion

# region refresh pairlist
@core.command('refresh-pairlist')
@click.option('-f', '--fiat-currency')
@click.option('--name', help='Name to save old whitelist', type=str)
@click.option(
    '-n',
    '--num-coins',
    help='The number of coins to trade with',
    type=int,
    default=50,
    show_default=True,
)
@click.option(
    '-l', '--log-friendly', is_flag=True, help='Display useful log information'
)
@click.pass_context
def refresh_pairlist(
    ctx, fiat_currency: str, num_coins: int, name: str, log_friendly: bool
):
    if not log_friendly:
        spinner.start()
    config = load_config(ctx.obj)

    if fiat_currency:
        config['stake_currency'] = fiat_currency.upper()

    static_pair_conf = config['pairlists'][0]
    config['pairlists'][0] = {
        "method": "VolumePairList",
        "number_assets": num_coins,
        "sort_key": "quoteVolume",
        "refresh_period": 1800,
    }
    config['pairlists'].append({"method": "AgeFilter", "min_days_listed": 100})
    config['pairlists'].append({"method": "PriceFilter", "low_price_ratio": 0.02})
    save_config(config, ctx.obj)
    output = []

    def extract_pairs(out: str):
        output.append(out.strip())
        logger.debug(out)

    sh.freqtrade('test-pairlist', c=ctx.obj['config_path'], _out=extract_pairs)
    logger.debug('Output: {}', output)
    pairs_str = output[1]
    pairs = pairs_str.strip('][').replace("'", '').split(', ')
    logger.debug('Exchange info before: {}', config['exchange']['pair_whitelist'])
    pairlist_path = Path(pair_names_json)
    pairlist_names = rapidjson.loads(pairlist_path.read_text())
    pairlist_names[name or datetime.today().strftime('%Y%m%d')] = {
        'list': pairs,
        'date': datetime.now().strftime('%Y-%m-%d-T%H:%M:%S'),
    }
    with pairlist_path.open(mode='w') as f:
        rapidjson.dump(pairlist_names, f, indent=2)
    config['exchange']['pair_whitelist'] = pairs
    # config['exchange']['pair_blacklist'].append('LINKDOWN/USDT')
    try:
        config['exchange']['pair_blacklist'] = list(
            set(config['exchange']['pair_blacklist'])
        )
    except KeyError:
        logger.warning(
            '"{}" has no blacklist. Creating empty list', ctx.obj['config_path']
        )
        config['exchange']['pair_blacklist'] = []
    config['pairlists'] = []
    config['pairlists'].append(static_pair_conf)
    save_config(config, ctx.obj)
    logger.debug(
        'Exchange info after: {}', load_config(ctx.obj)['exchange']['pair_whitelist']
    )
    if not log_friendly:
        spinner.stop()


# endregion

# region change-stake
@core.command('change-stake')
@click.argument('stake', type=str)
@click.option('-w', '--wallet-size', type=float, default=1000, show_default=True)
@click.option('-m', '--maximum-trades', type=float, default=10, show_default=True)
@click.pass_context
def change_stake(ctx, stake: str, wallet_size: float, maximum_trades: float):
    spinner.start()
    stake = stake.upper()
    config = load_config(ctx.obj)
    config['stake_currency'] = stake

    if stake == 'USDT' or stake == 'USDC':
        config['dry_run_wallet'] = wallet_size
        stake_amount = wallet_size / maximum_trades
        config['stake_amount'] = stake_amount
    else:
        dry_run_wallet = convert_price(stake, wallet_size)
        stake_amount = dry_run_wallet / maximum_trades
        config['dry_run_wallet'] = float(f'{dry_run_wallet: .8f}')
        config['stake_amount'] = float(f'{stake_amount: .8f}')

    save_config(config, ctx.obj)
    spinner.stop()


# endregion

# region hyperopt
@core.command('hyperopt', help='Returns the command for a hyperopt.')
@click.argument('strategy')
@click.option('-D', '--directory', type=str, help='The directory for the strategy.')
@click.option(
    '-S',
    '--spaces',
    type=str,
    required=True,
    help='Example for \'roi buy sell\': "--spaces rbs". Options:\t' + spaces_help,
)
@click.option(
    '-d',
    '--days',
    type=int,
    default=90,
    show_default=True,
    help='This will get the first 2/3rds of the days specified and convert it to a '
    'timerange. Similarly, backtest will use the last 1/3rd. '
    'This will only be used when --days is not provided',
)
@click.option('-t', '--timerange', type=str)
@click.option('-i', '--interval', type=str, default='1m', show_default=True)
@click.option('-c', '--config', type=click.Path(exists=True))
@click.option(
    '-l', '--loss-function', type=int, default=0, show_default=True, help=losses_help
)
@click.option('-e', '--epochs', type=int, default=10_000, show_default=True)
@click.option(
    '-E',
    '--epoch-intervals',
    type=int,
    default=100,
    show_default=True,
    help='The total number of epochs will be split this many intervals.'
    ' Fish terminal only',
)
@click.option('-m', '--min-trades', type=int, default=100, show_default=True)
@click.option('-p', '--pairs-name', type=str, default='')
@click.option(
    '--args',
    help='Additional args to add that are not covered here. Example: --args \'-j 3\'',
    default='',
)
@click.pass_context
def hyperopt(
    ctx,
    strategy,
    directory: str,
    spaces: str,
    days: int,
    timerange: str,
    interval: str,
    config: str,
    loss_function: int,
    epochs: int,
    epoch_intervals: int,
    min_trades,
    pairs_name: str,
    args: str,
):
    # parse spaces
    for s in spaces:
        if s not in spaces_dict:
            click.echo(f'{s} is not a recognized spaces option in:\n{spaces_help}')
            exit(1)
    spaces = ' '.join(set([spaces_dict.get(s) for s in spaces]))
    # parse days
    if not timerange:
        timerange = get_timerange(days, interval)
    if pairs_name:
        change_pairs(ctx, pairs_name)
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
    args_list.append(args)

    args_list.append(f" -c {config or ctx.obj['config_path']}")
    if not loss_function == 5:
        args_list.append(f' --hyperopt-loss {loss_func_dict[str(loss_function)]}')
    if directory:
        args_list.append(f" --strategy-path user_data/strategies/{directory}")
    if epoch_intervals > 1:
        args_list.append(';end')
    click.echo(' '.join(args_list))


# endregion

# region get ranges
@core.command('get-ranges')
@click.pass_context
@click.argument('interval', type=str)
@click.option('-d', '--max-days', type=int, help='The number of days to load')
@click.option('-c', '--computer-mode', is_flag=True, help='Only print dates')
def get_ranges(ctx, interval: str, max_days: int, computer_mode: bool):
    #  get infile
    gcv = get_config_value
    config = load_config(ctx.obj)
    pair: str = gcv(config, 'exchange.pair_whitelist')[0]
    pair = pair.replace('/', '_') + f'-{interval}' + '.json'
    exchange = config['exchange']['name']
    infile = Path(f'user_data/data/{exchange}', pair)

    # load data
    data = rapidjson.load(infile.open(), number_mode=rapidjson.NM_NATIVE)
    import pandas as pd

    df = pd.DataFrame(data=data, columns=DATA_COLUMNS)
    df['open_time'] = df['open_time'] / 1000
    last_date = Arrow.fromtimestamp(df.iloc[-1]['open_time'], tzinfo='utc')
    first_date = Arrow.fromtimestamp(df.iloc[0]['open_time'], tzinfo='utc')
    if max_days and last_date.shift(days=-max_days) > first_date:
        first_date = last_date.shift(days=-max_days)
    days_between = abs((first_date - last_date).days)

    two_thirds = round(days_between * (2 / 3))
    start_range = (first_date, first_date.shift(days=two_thirds))
    end_range = (start_range[1].shift(days=0), last_date)
    if computer_mode:
        print(
            f"{'-'.join([s.format(DATE_FORMAT) for s in start_range])},"
            f"{'-'.join([s.format(DATE_FORMAT) for s in end_range])}"
        )
    else:
        print(
            'For optimization:',
            '-'.join([s.format(DATE_FORMAT) for s in start_range]),
            f'\nFor back-testing:',
            '-'.join([s.format(DATE_FORMAT) for s in end_range]),
        )


# endregion

# region backtest
@core.command('backtest')
@click.pass_context
@click.argument('strategy', type=str)
@click.option('-D', '--directory', type=str, help='The directory for the strategy')
@click.option('-t', '--timerange', type=str)
@click.option('-d', '--days', type=int, default=60, show_default=True)
@click.option('-i', '--interval', type=str, default='5m', show_default=True)
@click.option('-p', '--pairs-name', type=str, default='')
@click.option('-w', '--min-win-rate', type=float, default=10, show_default=True)
@click.option(
    '-u', '--undo', is_flag=True, help='Undo pairlist changes after completed'
)
@click.option('-S', '--skip-post-processing', is_flag=True)
@click.option('-a', '--add-winners', is_flag=True)
@click.option('--as-command', is_flag=True)
def backtest(
    ctx,
    strategy: str,
    directory: str,
    timerange: str,
    days: int,
    interval: str,
    pairs_name: str,
    min_win_rate: float,
    undo: bool,
    skip_post_processing: bool,
    add_winners: bool,
    as_command: bool,
):
    output = []
    print(ctx.obj["config_path"])
    command = f'-s {strategy} -i {interval} -c {ctx.obj["config_path"]}'
    if not timerange:
        timerange = get_timerange(days, interval)
    if directory:
        command += f" --strategy-path user_data/strategies/{directory}"
    command += f" --timerange {timerange}"

    def printf(string):
        print(string, end='')
        output.append(string)

    spinner.start()
    config = load_config(ctx.obj)

    old_pairlist = config['exchange']['pair_whitelist']
    if as_command:
        click.echo('\nfreqtrade backtesting ' + command)
        return
    try:
        if pairs_name:
            change_pairs(ctx, pairs_name)
        spinner.stop()
        try:
            sh.freqtrade(['backtesting', *command.split(' ')], _out=printf, _err=printf)
        except Exception:
            exit(-3)
        if skip_post_processing:
            exit(0)
        # Parse output
        output = ''.join(output)
        report = BacktestOutputExtractor.create_report(output, min_win_rate)
        pprint(report.df)

        logfile = save_backtest_results(pairs_name, report)
        logfile.write_text(output)

        # TODO winners = winners.append(df.sum(numeric_only=True), ignore_index=True)

        report.print_winners()

        if add_winners:
            try:
                add_to_pairlist_name = (
                    input(
                        f'Add winners to which pairlist?{f" [{strategy.lower()}]" if pairs_name else ""}: '
                    )
                    or pairs_name
                )
            except KeyboardInterrupt:
                print('\nCTRL+c caught. Exiting without saving winners to pairlist')
                return
            if not add_to_pairlist_name:
                return
            PairListTools.add_to_pairlist(add_to_pairlist_name, report)
        print('log:', logfile)
    finally:
        if undo:
            config['exchange']['pair_whitelist'] = old_pairlist
            save_config(config, ctx.obj)
        spinner.stop()


# endregion

# region change pairlist
@core.command('change-pairlist')
@click.pass_context
@click.argument('pairs-name')
def change_pairlist_cli(ctx, pairs_name: str):
    config = load_config(ctx.obj)

    pairlist_names = rapidjson.loads(Path(pair_names_json).read_text())
    try:
        pairlist = pairlist_names[pairs_name]
    except KeyError:
        click.echo(f'\nCould not find pairlist: "{pairs_name}"')
        exit(1)
    config['exchange']['pair_whitelist'] = pairlist['list']
    save_config(config, ctx.obj)
    print('Pair list changed to:')
    print(pairlist['list'])


# endregion

# region new strategy
@core.command(
    help='Use templates from user_data/strategies/templates to create a new strategy'
)
@click.argument('template_name', type=str, required=True)
@click.argument('save_name', type=str, required=True)
@click.option(
    '-d',
    '--save-directory',
    type=str,
    help='Directory in user_data/strategies to save in. Default={template_name}',
)
@click.option('-r', '--replacement-data', type=str)
@click.option(
    '-l',
    '--from-latest',
    is_flag=True,
    help='Use the latest HyperOpt to make a strategy from a template',
)
@click.option('-o', '--override', is_flag=True, help='Override existing strategies')
def new_strategy(
    template_name: str,
    save_name: str,
    save_directory: str,
    replacement_data: str,
    from_latest: bool,
    override: bool,
):
    template_dir = 'user_data/strategies/templates'
    template_path = Path(template_dir, template_name)
    save_path = Path(
        'user_data/strategies/', save_directory or template_name, save_name + '.py'
    )
    cli = Bullet(
        prompt="\nPlease choose a template: ",
        choices=os.listdir(template_dir),
        indent=0,
        align=5,
        margin=2,
        shift=0,
        bullet="",
        pad_right=5,
        return_index=True,
    )
    save_path.parent.mkdir(exist_ok=True)
    try:
        save_path.touch(exist_ok=False)
    except Exception:
        if not override:
            click.echo(
                f'"{str(save_path)}" already exists. Pass -o/--override to override'
            )
            exit(1)
    if not template_path.exists():
        click.echo(f'Could not find template: \'{template_name}\'')
        exit(1)

    template_string = template_path.read_text()
    class_name = ''.join([s.capitalize() for s in save_name.split('_')])

    template = Template(template_string)
    best_result = get_best_result()
    parsed_replacement = eval(replacement_data if not from_latest else best_result)
    all_subs = [
        ele[1]
        for ele in Formatter().parse(template_string)
        if ele[1] and ' ' not in ele[1]
    ]
    empty_subs = {
        k: None for k in all_subs if k not in parsed_replacement and k != 'classname'
    }
    new_template = template.substitute(
        **parsed_replacement, **empty_subs, classname=class_name
    )
    save_path.write_text(new_template)
    click.echo('Saved to ' + str(save_path) + ' with name: ' + class_name)


# endregion

# region get best result
@core.command('getbestresult')
def get_best_result_cli():
    click.echo(get_best_result())


# endregion


if __name__ == '__main__':
    core()
