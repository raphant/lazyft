import pathlib

from lazyft import backtest, paths, models
from lazyft.backtest.commands import create_commands
from lazyft.backtest.runner import BacktestRunner
from lazyft.command_parameters import BacktestParameters
from lazyft.models import Strategy

paths.PARAMS_FILE = pathlib.Path(__file__).parent.joinpath('params.json')
paths.PARAMS_DIR = pathlib.Path(__file__).parent.joinpath('saved_params/')
param_id = 'test'
STRATEGY_WITH_ID = [Strategy(id='1')]
STRATEGIES = ['TestStrategy-test', 'TestStrategy']
config_name = 'config_test.json'

days = 5


def get_commands(strategies):
    cp = get_parameters(strategies)
    commands = create_commands(cp, verbose=True)
    return commands


def get_parameters(strategies):
    cp = BacktestParameters(
        strategies=strategies, config_path=config_name, days=days, download_data=False
    )
    return cp


def test_backtest_command_no_id():
    commands = get_commands(STRATEGIES)
    runner = BacktestRunner(commands[1])
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    assert bool(runner.report)
    runner.save()


def test_backtest_command_with_id():
    commands = get_commands(STRATEGY_WITH_ID)
    runner = BacktestRunner(commands[0])
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    assert bool(runner.report)
    # runner.report.json_file.unlink(missing_ok=True)
    runner.save()


# def test_id_pairlist():
#     """Make sure a pairlist can be extracted from a previous Hyperopt run"""
#     existing_report = get_hyperopt_repo().get_by_param_id(param_id)
#     pairlist = existing_report.pairlist
#     parameters = get_parameters(STRATEGY_WITH_ID)
#     assert parameters.config['exchange']['name'] == existing_report.exchange
#     parameters.pairs = []
#     strategy, id = parameters.strategy_id_pairs[0]
#     params_pairs = BacktestCommand(strategy, params=parameters, id=id).pairs
#     assert set(params_pairs) == set(pairlist)


# def test_backtest_with_generated_pairlist():
#     commands = backtest.create_commands(
#         strategies=STRATEGY, interval='5m', config=config_name, days=days
#     )
#     runner = backtest.BacktestRunner(commands.pop())
#     runner.execute()
#     report = runner.generate_report()
#     report.print_winners()


def test_save_backtesting_report():
    commands = get_commands(STRATEGY_WITH_ID)
    runner = BacktestRunner(commands[0])
    runner.execute()
    assert bool(runner.report)
    runner.save()


def test_multi_runner():
    commands = get_commands(STRATEGIES)
    mr = backtest.BacktestMultiRunner(commands)
    mr.execute()
    assert any(mr.reports)
    for r in mr.reports:
        assert isinstance(r, models.BacktestReport)
