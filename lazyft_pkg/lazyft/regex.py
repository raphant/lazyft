import re

# region hyperopt
RESULTS_REGEX = re.compile(
    r'Best \|\s+([\d/]+) \|\s+(?P<trades>\d+)\s\|\s+(?P<wins>\d+)\s+(?P<draws>\d+)\s+'
    r'(?P<losses>\d+) \|\s+(?P<profit>[\d.]+)% \|\s+(?P<avg_profit>[\d.]+) USD\s+'
    r'\([\d.]+%\) \| \d\sdays ..:..:.. \|\s+(?P<objective>-?[\d.]+)'
)
PICKLE_REGEX = re.compile(r"epochs saved to\s+'([\w\d_/.\-]+)")
FINAL_REGEX = re.compile(
    r'(?P<trades>\d+) trades.\s?(?P<wins>\d+)/(?P<draws>\d+)/(?P<losses>\d+) Wins/Draws/Losses. Avg profit\s+(?P<avg_profits>[\d.-]+)%. Median profit\s+(?P<med_profit>[\d.-]+)%. Total profit\s+(?P<tot_profit>[\d.-]+) \w+ \(\s+(?P<profit_percent>[\d.-]+)Σ?%?\). Avg duration (?P<avg_duration>(\d+ days?, ?)?.?.:..:..) min. Objective: (?P<loss>[\d.-]+)'
)
PARAM_REGEX = re.compile(r'({\"params\":{.+)')
SEED_REGEX = re.compile(r'Using optimizer random state: (\d+)')
EPOCH_LINE_REGEX = re.compile(
    r'(?P<epoch>[\d/]+)[\s|]+(?P<trades>[\d/]+)[\s|]+(?P<wins_draws_losses>\d+\s+\d+\s+\d+)[\s|]+(?P<average_profit>[\d.-]+%)[\s|]+(?P<profit>[\d.-]+ \w+\s+\([\d.-]+%\))[\s|]+(?P<average_duration>\d+ \w+ [\d:]+)[\s|]+(?P<max_drawdown>[\d.-]+ \w+\s+\([\d.]+%\))[\s|]+(?P<objective>[\d.-]+)'
)
CURRENT_EPOCH = re.compile(r'Epoch (?P<epoch>\d+)')
H_DATE_FROM_TO = re.compile(
    r'Hyperopting with data from (?P<from>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) up to '
    r'(?P<to>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
)
# endregion
# region backtesting
totals = r'(TOTAL)[^\d-]+(?P<sells>\d+)[^\d-]+(?P<avg_profit>[\d.-]+)[^\d-]+(?P<cum_profit>[\d.-]+)[^\d-]+(?P<total_profit_btc>[\d.-]+)[^\d-]+(?P<profit_percent>[\d.-]+)[^\d-]+(?P<avg_duration>[\d:]+)[^\d-]+(?P<wins>[\d.-]+)[^\d-]+(?P<draws>[\d.-]+)[^\d-]+(?P<losses>[\d.-]+)'

pair_totals = (
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
backtest_json = re.compile(r'(backtest-result[^\"]+)')
# endregion

# region Misc
strategy_files_pattern = re.compile(
    r'(\w+)[^\w]+(\w+.py)(?!.+LOAD FAILED)(?!.+DUPLICATE NAME)'
)
# endregion
