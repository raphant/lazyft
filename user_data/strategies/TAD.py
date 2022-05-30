# # --- Do not remove these libs ---
# from freqtrade.strategy.interface import IStrategy
# import pandas as pd
# from functools import reduce
# from pandas import DataFrame
# # --------------------------------
# from queue import Queue # Python 3.x
# import threading
# from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import BinanceWebSocketApiManager
# import talib.abstract as ta
# from freqtrade.strategy import merge_informative_pair
# import freqtrade.vendor.qtpylib.indicators as qtpylib
# from freqtrade.strategy import DecimalParameter
# from datetime import datetime, timedelta
# from freqtrade.optimize.space import SKDecimal
# from skopt.space import  Dimension, Integer
# from typing import Dict, List
# import math
#
#
# ####################################   Tip and Dip by Chillie   ###########################################
# #
# #
# #
# #
# # Dry-run only, can't run backtesting as strat relies on live data
# # Don't recommend running it live, as I dont consider it properly tested yet
# #
# #
# #   if you run with docker
# #   add this to your docker.custom file and build the image (check documentation for this part)
# #   RUN pip install unicorn-binance-websocket-api
# #
# ###########################################################################################################
# # Use this in config:
# #     "max_open_trades": 2 - 4
# #     "stake_amount": "unlimited",
# #     "timeframe": "1m"
# #
# # read in documentation about this part
# #     "bid_strategy": {
# #        "use_order_book": true,
# #		"price_side":"bid",
# #        "order_book_top": 3
# #    },
# #    "ask_strategy": {
# #        "use_order_book": true,
# #        "order_book_top": 3,
# #		"price_side": "ask"
# #    },
# #
# #   Fast access to binance, might get you banned for 24h, didnt get banned so far so its probably fine
# #   The ThrededFunction takes updates every second so this limits rateLimit internaly
# #
# #   "ccxt_config": {
# #			"enableRateLimit": true,
# #			"rateLimit": 10
# #		},
# #
# #
# #   for internal wait, this is handled by the ThreadedFunction as it updates every second default is 5 sec
# #   "internals": {
# #		"process_throttle_secs": 0
# #	}
# #
# #
# # We dont want trades to linger too long
# #    "unfilledtimeout": {
# #		"buy": 1,
# #		"sell": 1
# #	},
# #
# #     RangeStabilityFilter --> "lookback_days": 1 // "min_rate_of_change": 0.20
# #     Volume filter after it with "number_assets": 25 - 45 <-- leaving smaller coins is riskier
# #
# #
# #
# #
# ###########################################################################################################
# #   DONATION
# #   Not required, but if you want to help a student out it would be appreciated
# #
# #   BTC:                       1QwLM9Zfd5dj8KteAMnyaAePsdNqJnepm
# #   ETH (ERC20):               0xe3203d2aadea409d644e25841567a329d9b121ab
# #
# ###########################################################################################################
#
# class TAD(IStrategy):
#     class HyperOpt:
#         @staticmethod
#         def generate_roi_table(params: Dict) -> Dict[int, float]:
#             """
#             Create a ROI table.
#
#             Generates the ROI table that will be used by Hyperopt.
#             You may override it in your custom Hyperopt class.
#             """
#             roi_table = {}
#             roi_table[0] = params['roi_p1'] + params['roi_p2'] + params['roi_p3'] + params['roi_p4'] + params['roi_p5'] + params['roi_p6'] + params['roi_p7'] + params['roi_p8']
#             roi_table[params['roi_t8']] = params['roi_p1'] + params['roi_p2'] + params['roi_p3'] + params['roi_p4'] + params['roi_p5'] + params['roi_p6'] + params['roi_p7']
#             roi_table[params['roi_t8'] + params['roi_t7']] = params['roi_p1'] + params['roi_p2'] + params['roi_p3'] + params['roi_p4'] + params['roi_p5'] + params['roi_p6']
#             roi_table[params['roi_t8'] + params['roi_t7'] + params['roi_t6']] = params['roi_p1'] + params['roi_p2'] + params['roi_p3'] + params['roi_p4'] + params['roi_p5']
#             roi_table[params['roi_t8'] + params['roi_t7'] + params['roi_t6'] + params['roi_t5']] = params['roi_p1'] + params['roi_p2'] + params['roi_p3'] + params['roi_p4']
#             roi_table[params['roi_t8'] + params['roi_t7'] + params['roi_t6'] + params['roi_t5'] + params['roi_t4']] = params['roi_p1'] + params['roi_p2'] + params['roi_p3']
#             roi_table[params['roi_t8'] + params['roi_t7'] + params['roi_t6'] + params['roi_t5'] + params['roi_t4'] + params['roi_t3']] = params['roi_p1'] + params['roi_p2']
#             roi_table[params['roi_t8'] + params['roi_t7'] + params['roi_t6'] + params['roi_t5'] + params['roi_t4'] + params['roi_t3'] + params['roi_t2']] = params['roi_p1']
#             roi_table[params['roi_t8'] + params['roi_t7'] + params['roi_t6'] + params['roi_t5'] + params['roi_t4'] + params['roi_t3'] + params['roi_t2'] + params['roi_t1']] = 0
#
#             return roi_table
#
#         @staticmethod
#         def roi_space() -> List[Dimension]:
#             """
#             Create a ROI space.
#
#             Defines values to search for each ROI steps.
#
#             This method implements adaptive roi hyperspace with varied
#             ranges for parameters which automatically adapts to the
#             timeframe used.
#
#             It's used by Freqtrade by default, if no custom roi_space method is defined.
#             """
#
#             # Default scaling coefficients for the roi hyperspace. Can be changed
#             # to adjust resulting ranges of the ROI tables.
#             # Increase if you need wider ranges in the roi hyperspace, decrease if shorter
#             # ranges are needed.
#             roi_t_alpha = 1.0
#             roi_p_alpha = 1.0
#
#             timeframe_min = 1
#
#             # We define here limits for the ROI space parameters automagically adapted to the
#             # timeframe used by the bot:
#             #
#             # * 'roi_t' (limits for the time intervals in the ROI tables) components
#             #   are scaled linearly.
#             # * 'roi_p' (limits for the ROI value steps) components are scaled logarithmically.
#             #
#             # The scaling is designed so that it maps exactly to the legacy Freqtrade roi_space()
#             # method for the 5m timeframe.
#             roi_t_scale = timeframe_min / 1
#             roi_p_scale = math.log1p(timeframe_min) / math.log1p(5)
#             roi_limits = {
#                 'roi_t1_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t1_max': int(600 * roi_t_scale * roi_t_alpha),
#                 'roi_t2_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t2_max': int(450 * roi_t_scale * roi_t_alpha),
#                 'roi_t3_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t3_max': int(300 * roi_t_scale * roi_t_alpha),
#                 'roi_t4_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t4_max': int(250 * roi_t_scale * roi_t_alpha),
#                 'roi_t5_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t5_max': int(200 * roi_t_scale * roi_t_alpha),
#                 'roi_t6_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t6_max': int(150 * roi_t_scale * roi_t_alpha),
#                 'roi_t7_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t7_max': int(100 * roi_t_scale * roi_t_alpha),
#                 'roi_t8_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_t8_max': int(50 * roi_t_scale * roi_t_alpha),
#                 'roi_t8_min': int(1 * roi_t_scale * roi_t_alpha),
#                 'roi_p1_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p1_max': 0.075 * roi_p_scale * roi_p_alpha,
#                 'roi_p2_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p2_max': 0.10 * roi_p_scale * roi_p_alpha,
#                 'roi_p3_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p3_max': 0.125 * roi_p_scale * roi_p_alpha,
#                 'roi_p4_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p4_max': 0.15 * roi_p_scale * roi_p_alpha,
#                 'roi_p5_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p5_max': 0.175 * roi_p_scale * roi_p_alpha,
#                 'roi_p6_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p6_max': 0.20 * roi_p_scale * roi_p_alpha,
#                 'roi_p7_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p7_max': 0.25 * roi_p_scale * roi_p_alpha,
#                 'roi_p8_min': 0.002 * roi_p_scale * roi_p_alpha,
#                 'roi_p8_max': 0.30 * roi_p_scale * roi_p_alpha,
#             }
#             p = {
#                 'roi_t1': roi_limits['roi_t1_min'],
#                 'roi_t2': roi_limits['roi_t2_min'],
#                 'roi_t3': roi_limits['roi_t3_min'],
#                 'roi_t4': roi_limits['roi_t4_min'],
#                 'roi_t5': roi_limits['roi_t5_min'],
#                 'roi_t6': roi_limits['roi_t6_min'],
#                 'roi_t7': roi_limits['roi_t7_min'],
#                 'roi_t8': roi_limits['roi_t8_min'],
#                 'roi_p1': roi_limits['roi_p1_min'],
#                 'roi_p2': roi_limits['roi_p2_min'],
#                 'roi_p3': roi_limits['roi_p3_min'],
#                 'roi_p4': roi_limits['roi_p4_min'],
#                 'roi_p5': roi_limits['roi_p5_min'],
#                 'roi_p6': roi_limits['roi_p6_min'],
#                 'roi_p7': roi_limits['roi_p7_min'],
#                 'roi_p8': roi_limits['roi_p8_min'],
#             }
#             p = {
#                 'roi_t1': roi_limits['roi_t1_max'],
#                 'roi_t2': roi_limits['roi_t2_max'],
#                 'roi_t3': roi_limits['roi_t3_max'],
#                 'roi_t4': roi_limits['roi_t4_max'],
#                 'roi_t5': roi_limits['roi_t5_max'],
#                 'roi_t6': roi_limits['roi_t6_max'],
#                 'roi_t7': roi_limits['roi_t7_max'],
#                 'roi_t8': roi_limits['roi_t8_max'],
#                 'roi_p1': roi_limits['roi_p1_max'],
#                 'roi_p2': roi_limits['roi_p2_max'],
#                 'roi_p3': roi_limits['roi_p3_max'],
#                 'roi_p4': roi_limits['roi_p4_max'],
#                 'roi_p5': roi_limits['roi_p5_max'],
#                 'roi_p6': roi_limits['roi_p6_max'],
#                 'roi_p7': roi_limits['roi_p7_max'],
#                 'roi_p8': roi_limits['roi_p8_max'],
#             }
#
#             return [
#                 Integer(roi_limits['roi_t1_min'], roi_limits['roi_t1_max'], name='roi_t1'),
#                 Integer(roi_limits['roi_t2_min'], roi_limits['roi_t2_max'], name='roi_t2'),
#                 Integer(roi_limits['roi_t3_min'], roi_limits['roi_t3_max'], name='roi_t3'),
#                 Integer(roi_limits['roi_t4_min'], roi_limits['roi_t4_max'], name='roi_t4'),
#                 Integer(roi_limits['roi_t5_min'], roi_limits['roi_t5_max'], name='roi_t5'),
#                 Integer(roi_limits['roi_t6_min'], roi_limits['roi_t6_max'], name='roi_t6'),
#                 Integer(roi_limits['roi_t7_min'], roi_limits['roi_t7_max'], name='roi_t7'),
#                 Integer(roi_limits['roi_t8_min'], roi_limits['roi_t8_max'], name='roi_t8'),
#                 SKDecimal(roi_limits['roi_p1_min'], roi_limits['roi_p1_max'], decimals=3, name='roi_p1'),
#                 SKDecimal(roi_limits['roi_p2_min'], roi_limits['roi_p2_max'], decimals=3, name='roi_p2'),
#                 SKDecimal(roi_limits['roi_p3_min'], roi_limits['roi_p3_max'], decimals=3, name='roi_p3'),
#                 SKDecimal(roi_limits['roi_p4_min'], roi_limits['roi_p4_max'], decimals=3, name='roi_p4'),
#                 SKDecimal(roi_limits['roi_p5_min'], roi_limits['roi_p5_max'], decimals=3, name='roi_p5'),
#                 SKDecimal(roi_limits['roi_p6_min'], roi_limits['roi_p6_max'], decimals=3, name='roi_p6'),
#                 SKDecimal(roi_limits['roi_p7_min'], roi_limits['roi_p7_max'], decimals=3, name='roi_p7'),
#                 SKDecimal(roi_limits['roi_p8_min'], roi_limits['roi_p8_max'], decimals=3, name='roi_p8'),
#             ]
#
#     #initialize connection to datastream (this starts up on all strategies you run so comment it out if you are not using this strat)
#     binance_websocket_api_manager = BinanceWebSocketApiManager(exchange="binance.com")
#
#     tickerData = pd.DataFrame()
#     # Sell signal
#     exit_sell_signal = False
#     sell_profit_offset = 0.001 # it doesn't meant anything, just to guarantee there is a minimal profit.
#     ignore_roi_if_buy_signal = False
#     # Custom stoploss
#     use_custom_stoploss = True
#     # Run "populate_indicators()" only for new candle.
#     process_only_new_candles = False
#     # Number of candles the strategy requires before producing valid signals
#     exit_sell_signal = False
#     sell_profit_only = False
#
#     # Optional order type mapping.
#     order_types = {
#         'buy': 'limit',
#         'sell': 'limit',
#         'stoploss': 'market',
#         'stoploss_on_exchange': False
#     }
#     # ROI table:
#     minimal_roi = {
#         "0": 0.013,
#         "2": 0.004,
#         "8": 0.003,
#         "10": 0.001,
#         "16": 0
#     }
#
#     # Stoploss:
#     stoploss = -0.99
#
#     def informative_pairs(self):
#         # get access to all pairs available in whitelist.
#         pairs = self.dp.current_whitelist()
#         # Assign tf to each pair so they can be downloaded and cached for strategy.
#         informative_pairs = [(pair, '5m') for pair in pairs]
#         return informative_pairs
#
#
#     def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         if not self.dp:
#             # Don't do anything if DataProvider is not available.
#             return dataframe
#         # Get the informative pair
#         informative_5m = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='5m')
#         # Get the 14 day rsi
#         dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
#
#         #dont trade on sundays til monday 6am
#         dataframe['dontbuy'] = ((dataframe['date'].dt.dayofweek == 6) & (dataframe['date'].dt.hour >= 6)) | ((dataframe['date'].dt.dayofweek == 0) & (dataframe['date'].dt.hour < 6))
#         return dataframe
#
#     #Function that runs on every loop start and gets data from the binance miniTicker stream
#     def ThreadedFunction (self):
#         oldest_stream_data_from_stream_buffer = self.binance_websocket_api_manager.pop_stream_data_from_stream_buffer()
#         if oldest_stream_data_from_stream_buffer:
#             tickerData = oldest_stream_data_from_stream_buffer
#             return tickerData
#
#     def bot_loop_start(self, *kwargs) -> None:
#         que = Queue()
#         x = threading.Thread(target=que.put(self.ThreadedFunction()), daemon=True)
#         x.start()
#         x.join()
#         #the Que enables the return from the threaded function
#         self.tickerData = que.get()
#         return
#
#     # deletes the first candle in the dataframe(the one thats 16h old, so it doesn't matter) creates the new one on index 998 with current data
#     def extractValuesFromTicker(self, dataframe: DataFrame, strippedPair: str,):
#         #reads last tick data
#         tickData = pd.read_json(self.tickerData)
#
#         #Copies last time and adds one minute
#         date = dataframe.loc[998,'date'] + timedelta(minutes=1)
#
#         #for trading on sundays/monday mornings
#         dontbuy = dataframe.loc[998,'dontbuy']
#
#         #map candle data to index to pandas series
#         extractedValues=tickData.loc[tickData['s']==strippedPair,['c','o','h','l']]
#         extractedValues.columns = ['close', 'open', 'high','low']
#         extractedValues['date'] = date
#         extractedValues['dontbuy'] = dontbuy
#
#         #add data to the 998 candle
#         dataframe = pd.concat([dataframe, extractedValues], ignore_index = True, axis = 0)
#
#         #drop first candle so the FT doesn't warn about too long dataframe, moves the index back
#         dataframe = dataframe.drop([1]).reset_index(drop=True)
#         #calculate RSI for generated candle
#         dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
#
#         #if you want to test out candle generation, 998 check is here becouse if no new data is available (no trades made) for the candle it will not be present in the ticker data
#         #print(strippedPair)
#         #if (998 in dataframe.index.values):
#         #    print(dataframe.tail(5))
#         return dataframe
#
#     #terminate the trade if it takes longer than 20 min
#     def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
#                         current_rate: float, current_profit: float, **kwargs) -> float:
#         if  (current_time - timedelta(minutes=20) > trade.open_date_utc):
#             return 0.01
#         return 1
#
#     def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         conditions = []
#
#         #takes pair name from metadata [pair] and analises the data only for the current pair
#         dataframe = self.extractValuesFromTicker(dataframe, metadata['pair'].replace('/', ''))
#
#
#         #998 check is here becouse if no new data is available (no trades made) for the candle it will not be present in the ticker data
#         if (998 in dataframe.index.values):
#             #print(metadata['pair'])
#             #print(qtpylib.crossed_above(dataframe[986:993]['rsi'], 41.7).any())
#             #print(qtpylib.crossed_below(dataframe[993:998]['rsi'], 51.8).any())
#             #print(dataframe.loc[998,'rsi'] <  44.4)
#             #writing conditions in this way gives the ability to set the buy_tag, this prints when buy order is created
#             #logic
#             buy_01_logic = []
#             #this is a nice one --> if any of the candle in the range 982 to range 998 (so last 20 minutes) crossed below the 66.7 RSI it returns True
#             #doesn't work in backtresting, as backtesting goes trough the whole dataframe at once, function for backtesting at the bottom
#             #multiple of these can be used in conjecture to trade the specific patern, check buy_08
#             buy_01_logic.append(qtpylib.crossed_below(dataframe[989:998]['rsi'], 66.7).any())
#
#             #if RSI dropped to 36.6 after crossing below 66.7 in last 20 mins buy signal is sent
#             #this looks at the 998 candle, which is updated ever sec or so
#             buy_01_logic.append(dataframe.loc[998,'rsi'] < 36.6)
#
#             #for sundays and mondays
#             buy_01_logic.append(dataframe['dontbuy'] == False)
#             buy_01_logic.append(dataframe['volume'] > 0)
#
#             # Populate
#             # Add it to the conditions list
#             dataframe['buy_01_trigger'] = reduce(lambda x, y: x & y, buy_01_logic)
#             conditions.append(dataframe['buy_01_trigger'])
#             if dataframe.loc[998,'buy_01_trigger']:
#                 dataframe[998,'buy_tag'] = "buy_01_trigger"
#
#
#             #logic
#             buy_02_logic = []
#             buy_02_logic.append(qtpylib.crossed_below(dataframe[989:998]['rsi'], 66.7).any())
#             buy_02_logic.append(dataframe.loc[998,'rsi'] <  36.6)
#             buy_02_logic.append(dataframe['dontbuy'] == False)
#             # Populate
#             dataframe['buy_02_trigger'] = reduce(lambda x, y: x & y, buy_02_logic)
#             conditions.append(dataframe['buy_02_trigger'])
#             if dataframe.loc[998,'buy_02_trigger']:
#                 dataframe[998,'buy_tag'] = "buy_02_trigger"
#                 #print(dataframe.tail(30))
#
#
#             #logic
#             buy_03_logic = []
#             buy_03_logic.append(qtpylib.crossed_below(dataframe[989:998]['rsi'], 74.6).any())
#             buy_03_logic.append(dataframe.loc[998,'rsi'] < 43.5)
#             buy_03_logic.append(dataframe['dontbuy'] == False)
#             # Populate
#             dataframe['buy_03_trigger'] = reduce(lambda x, y: x & y, buy_03_logic)
#             conditions.append(dataframe['buy_03_trigger'])
#             if dataframe.loc[998,'buy_03_trigger']:
#                 dataframe[998,'buy_tag'] = "buy_03_trigger"
#                 #print(dataframe.tail(30))
#
#
#             #logic
#             buy_04_logic = []
#             buy_04_logic.append(qtpylib.crossed_below(dataframe[989:998]['rsi'], 89.4).any())
#             buy_04_logic.append(dataframe.loc[998,'rsi'] < 39.3)
#             buy_04_logic.append(dataframe['dontbuy'] == False)
#             # Populate
#             dataframe['buy_04_trigger'] = reduce(lambda x, y: x & y, buy_04_logic)
#             conditions.append(dataframe['buy_04_trigger'])
#             if dataframe.loc[998,'buy_04_trigger']:
#                 dataframe[998,'buy_tag'] = "buy_04_trigger"
#                 #print(dataframe.tail(30))
#
#
#             #logic
#             buy_05_logic = []
#             buy_05_logic.append(qtpylib.crossed_below(dataframe['rsi'], 19.6))
#             buy_05_logic.append(dataframe['dontbuy'] == False)
#             # Populate
#             dataframe['buy_05_trigger'] = reduce(lambda x, y: x & y, buy_05_logic)
#             conditions.append(dataframe['buy_05_trigger'])
#             if dataframe.loc[998,'buy_05_trigger']:
#                 dataframe[998,'buy_tag'] = "buy_05_trigger"
#                 #print(dataframe.tail(30))
#
#
#             #logic
#             buy_06_logic = []
#             buy_06_logic.append(qtpylib.crossed_below(dataframe[980:993]['rsi'], 31.5).any())
#             buy_06_logic.append(qtpylib.crossed_below(dataframe[989:998]['rsi'], 59.2).any())
#             buy_06_logic.append(dataframe.loc[998,'rsi'] <33.3)
#             buy_06_logic.append(dataframe['dontbuy'] == False)
#
#             # Populate
#             dataframe['buy_06_trigger'] = reduce(lambda x, y: x & y, buy_06_logic)
#             conditions.append(dataframe['buy_06_trigger'])
#             if dataframe.loc[998,'buy_06_trigger']:
#                 dataframe[998,'buy_tag'] = "buy_06_trigger"
#                 #print(dataframe.tail(30))
#
#             """
#             #logic
#             buy_07_logic = []
#             buy_07_logic.append(dataframe.loc[998,'rsi'] <  77.2)
#             buy_07_logic.append(dataframe['dontbuy'] == False)
#             # Populate
#             dataframe['buy_07_trigger'] = reduce(lambda x, y: x & y, buy_07_logic)
#             conditions.append(dataframe['buy_07_trigger'])
#             if dataframe.loc[998,'buy_07_trigger']:
#                 dataframe[998,'buy_tag'] = "buy_07_trigger"
#                 #print(dataframe.tail(30))
#             """
#
#             #check if any of the conditions are True
#             if conditions:
#                 dataframe.loc[
#                     reduce(lambda x, y: x | y, conditions),
#                     'buy'
#                 ] = 1
#
#         #If no new data is present (998 check from the top), don't trade
#         else:
#             dataframe['buy'] = 0
#         return dataframe
#
#
#     def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
#         dataframe.loc[
#             #no sell signals, fully relies on ROI
#             (
#                 (False) &
#                 (dataframe['volume'] > 0)
#             ),
#             'sell'] = 1
#         return dataframe
#
#
#
#     #remove dataframe checks from the freqtrade, not really elegant but it works
#     def assert_df(self, dataframe: DataFrame, df_len: int, df_close: float, df_date: datetime):
#         """
#         Ensure dataframe (length, last candle) was not modified, and has all elements we need.
#         """
#         message_template = "Dataframe returned from strategy has mismatching {}."
#
#
#
#
#
#
