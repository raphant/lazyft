from solipsis5 import Solipsis


class StudySolipsis_ETH(Solipsis):

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
