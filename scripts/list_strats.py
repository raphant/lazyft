from freqtrade.commands import start_list_strategies, Arguments

from lazyft.config import Config

param_id = 'test'
# STRATEGY_WITH_ID = [Strategy(id=1)]
STRATEGIES = ['BatsContest']
config = Config('config.1.18.22.json')
secrets = Config('binancecom.json')

args = [
    "list-strategies",
]
start_list_strategies(Arguments(args).get_parsed_arg())
