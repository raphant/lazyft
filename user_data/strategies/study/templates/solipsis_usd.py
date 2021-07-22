import json
import pathlib

from solipsis5 import StudySolipsis

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent.absolute()

# --------------------------------


# noinspection DuplicatedCode
param_file_id = '$NAME'
params_file = pathlib.Path(SCRIPT_DIRECTORY, 'params.json')


def load():
    if '$' in param_file_id or not params_file.exists():
        return {}
    params = json.loads(params_file.read_text())
    return params['StudySolipsis5'][param_file_id]['params']


class StudySolipsis_USD(StudySolipsis):

    timeframe = '5m'
    inf_timeframe = '1h'

    minimal_roi = {"0": 100}

    buy_params = {}

    sell_params = {}

    stoploss = -0.10

    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = False

    startup_candle_count: int = 233
    process_only_new_candles = False

    custom_trade_info = {}
    custom_fiat = "USD"
    custom_btc_inf = False
    locals().update(load())
