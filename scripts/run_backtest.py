from lazyft.backtest.commands import create_commands
from lazyft.backtest.runner import BacktestRunner
from lazyft.command_parameters import BacktestParameters

param_id = 'test'
# STRATEGY_WITH_ID = [Strategy(id=1)]
STRATEGIES = ['TestStrategy-test', 'TestStrategy']
config_name = 'config_test.json'

days = 10

if __name__ == '__main__':
    cp = BacktestParameters(
        strategies=STRATEGIES,
        config_path=config_name,
        days=days,
        download_data=True,
        inf_interval='1h 1d',
    )
    commands = create_commands(cp, verbose=True)
    runner = BacktestRunner(commands[1], load_from_hash=False)
    runner.execute()
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    assert bool(runner.report)
    # runner.save()
