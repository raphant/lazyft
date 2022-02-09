from lazyft.config import Config

from lazyft.pairlist import refresh_pairlist

param_id = 'test'
# STRATEGY_WITH_ID = [Strategy(id=1)]
STRATEGIES = ['BatsContest']
config_name = 'config.json'
config = Config(config_name)
days = 365

if __name__ == '__main__':
    print(refresh_pairlist(config, n_coins=11, save_as='config.1.18.22.json'))
    # runner.save()
