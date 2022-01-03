from lazyft.command import create_commands
from lazyft.command_parameters import HyperoptParameters
from lazyft.hyperopt import HyperoptRunner

param_id = 'test'
# STRATEGY_WITH_ID = [Strategy(id=1)]
STRATEGIES = ['TestStrategy']
config_name = 'config.json'

days = 10

if __name__ == '__main__':
    hp = HyperoptParameters(
        strategies=STRATEGIES,
        config_path=config_name,
        epochs=30,
        spaces='roi stoploss',
        min_trades=1,
        days=days,
        download_data=False,
    )
    commands = create_commands(hp, verbose=True)
    runner = HyperoptRunner(commands[0])
    runner.execute(background=True)
    if runner.error:
        raise runner.exception
    assert bool(runner.report)
    print(runner.report)
    # runner.save()
