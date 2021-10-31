import re

# region hyperopt
# 5 epochs saved to 'user_data/hyperopt_results/strategy_TestStrategy3_2021-10-04_08-03-48.fthypt'.
PICKLE_REGEX = re.compile(r"epochs saved to\s+'([\w\d_/.\-]+)")
# 50 trades. 29/19/2 Wins/Draws/Losses. Avg profit   0.57%. Median profit   1.00%. Total profit  27.87894615 USD (   5.58%). Avg duration 21:56:00 min. Objective: -1658.24169
FINAL_REGEX = re.compile(
    r'(?P<trades>\d+) trades.\s?(?P<wins>\d+)/(?P<draws>\d+)/'
    r'(?P<losses>\d+) Wins/Draws/Losses. Avg profit\s+'
    r'(?P<avg_profits>[\d.-]+)%. Median profit\s+'
    r'(?P<med_profit>[\d.-]+)%. Total profit\s+'
    r'(?P<tot_profit>[\d.-]+) \w+ \(\s+'
    r'(?P<profit_percent>[\d.-]+)Σ?%?\). Avg duration '
    r'(?P<avg_duration>(\d+ days?, ?)?.?.:..:..) min. Objective: '
    r'(?P<loss>[\d.-]+)'
)
PARAM_REGEX = re.compile(r'({\"params\":{.+)')
SEED_REGEX = re.compile(r'Using optimizer random state: (\d+)')

# | * Best |  10/100 |       47 |     18   27    2 |        0.50% |        22.113 USD    (4.42%) |
EPOCH_LINE_REGEX = re.compile(
    r'(?P<epoch>[\d/]+)[\s|]+(?P<trades>[\d/]+)[\s|]+'
    r'(?P<wins_draws_losses>\d+\s+\d+\s+\d+)[\s|]+'
    r'(?P<average_profit>[\d.-]+%)[\s|]+'
    r'(?P<profit>[\d.-]+ \w+\s+\([\d.,-]+%\))[\s|]+'
    r'(?P<average_duration>\d+ \w+ [\d:]+)[\s|]+'
    r'(?P<max_drawdown>(?:[\d.-]+ (\w+\s+)\([\d.]+%\))?(?:--)?)[\s|]+'
    r'(?P<objective>[\d.,-]+)'
)
# [Epoch 100 of 100 (100%)] ||         | [Time:  0:00:53, Elapsed Time: 0:00:53]
CURRENT_EPOCH = re.compile(r'Epoch (?P<epoch>\d+)')
# freqtrade.optimize.hyperopt - INFO - Hyperopting with data from 2021-08-01 00:00:00 up to
H_DATE_FROM_TO = re.compile(
    r'Hyperopting with data from (?P<from>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) up to '
    r'(?P<to>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
)
# endregion

# region backtesting
totals = r'(TOTAL)[^\d-]+(?P<sells>\d+)[^\d-]+(?P<avg_profit>[\d.-]+)[^\d-]+(?P<cum_profit>[\d.-]+)[^\d-]+(?P<total_profit_btc>[\d.-]+)[^\d-]+(?P<profit_percent>[\d.-]+)[^\d-]+(?P<avg_duration>[\d:]+)[^\d-]+(?P<wins>[\d.-]+)[^\d-]+(?P<draws>[\d.-]+)[^\d-]+(?P<losses>[\d.-]+)'
# | MATIC/USD |      2 |           0.22 |           0.44 |            0.433 |           0.09 |        5:40:00 |     1     0     1  50.0 |
# |   SOL/USD |      3 |           0.14 |           0.43 |            0.427 |           0.09 |        3:45:00 |     1     1     1  33.3 |
pair_totals = re.compile(
    r'(?P<pair>\w+/\w+)[^\d-]+(?P<sells>\d+)[^\d-]+(?P<avg_profit>[\d.-]+)[^\d-]+'
    r'(?P<cum_profit>[\d.-]+)[^\d-]+(?P<total_profit_btc>[\d.-]+)[^\d-]+'
    r'(?P<profit_percent>[\d.-]+)[^\d-]+(?P<avg_duration>(\d+ days?, ?)?.?.:..:?.?.?)'
    r'[^\d-]+(?P<wins>[\d.-]+)[^\d-]+(?P<draws>[\d.-]+)[^\d-]+(?P<losses>[\d.-]+)'
    r'[^\d-]+(?P<win_percent>[\d.-]+)'
)
b_from_ = r'Backtesting from[^\d]+(?P<date_from>\d{4}-\d{2}-\d{2} [\d:]+)'
b_to = r'Backtesting to[^\d]+(?P<date_to>\d{4}-\d{2}-\d{2} [\d:]+)'

first_trade = r'First trade[^\d]+(?P<first_trade>\d{4}-\d{2}-\d{2} [\d:]+)'
trades_per_day = r'Trades per day[^\d]+(?P<trades_per_day>[\d.]+)'
total_trades = r'Total trades[^\d]+(?P<total_trades>[\d.]+)'
# dumping json to "user_data/backtest_results/backtest-result-2021-10-04_08-58-46.json"
backtest_json = re.compile(r'(backtest-result[^\"]+)')
# endregion

# region Misc
strategy_files_pattern = re.compile(
    r'(\w+)[^\w]+(\w+.py)(?!.+LOAD FAILED)(?!.+DUPLICATE NAME)'
)
# endregion
