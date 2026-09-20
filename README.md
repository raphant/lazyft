# LazyFT

LazyFT wraps [FreqTrade](https://github.com/freqtrade/freqtrade) so that every backtest and hyperopt you run becomes a saved, queryable record instead of terminal output you lose.
Each run is stored with the strategy code, pairlist, and config that produced it, so you can come back months later and ask how a given pair performed across your entire history.

**This software is no longer actively maintained, but FreqTrade is.**
LazyFT targets `freqtrade[hyperopt]==2023.2` and has not been updated since.
FreqTrade has kept shipping monthly releases in the years since, so some of what LazyFT adds here may now exist in FreqTrade itself, and some of it may no longer work against a current release.
Check against the FreqTrade version you actually run before relying on any of it.

## The problem it solves

Optimizing a FreqTrade strategy means running a hyperopt, copying the winning parameters into a file, running a backtest, editing the strategy, running another hyperopt, and trying to remember which parameter file went with which version of the code.
The results live in your scrollback.
A week later you cannot reconstruct which run produced which numbers.

LazyFT keeps the record for you.

Instead of manually deleting and re-adding parameter files between runs, you pass a hyperopt ID and LazyFT swaps the right parameters in and out.

Instead of results going stale the moment you edit your strategy, LazyFT saves a copy of the strategy after each hyperopt, so the numbers stay attached to the code behind them.

Instead of checking whether you have candle data before every run, LazyFT checks and downloads whatever is missing.

Instead of hand-rolling multi-stage optimization, `SpaceHandler` lets you enable and disable custom hyperopt spaces programmatically, so a sequence of hyperopts and backtests can run unattended and notify you when it finishes.

## What you can ask it

Runs are stored in a local SQLite database rather than printed, so the repository answers questions the raw tool cannot.

```python
from lazyft.reports import get_backtest_repo, get_hyperopt_repo

# How has every pair performed across every backtest I have ever saved?
get_backtest_repo().get_pair_totals()

# What did all my strategies do over a specific date range?
get_backtest_repo().get_results_from_date_range('20220101', '20220201')

# Which strategies have performed best?
get_backtest_repo().get_top_strategies(n=3)

# Show me one strategy's whole backtest history, most profitable first.
get_backtest_repo().filter_by_strategy(['Strategy']).sort_by_profit().df()

# And the hyperopt history.
get_hyperopt_repo().df()
```

Every report also carries the pairlist and config settings of the run that produced it, and the exact strategy source:

```python
from lazyft.models import StrategyBackup

report = get_hyperopt_repo().get(1)
StrategyBackup.load_hash(report.strategy_hash).print()
StrategyBackup.load_hash(report.strategy_hash).export_to('./recovered/')
```

## Getting started

### Caution

LazyFT was written for one setup and released afterwards.
It expects Linux, a FreqTrade environment installed without Docker, and FreqTrade 2023.2.
Remote bot management assumes SSH keys are already installed on the target server.

If your setup matches, getting started should be simple.
If it does not, expect friction, especially when running backtests and hyperopts through Docker.

### Installation

#### Install in a FreqTrade environment (recommended)

If you have not already, clone a FreqTrade environment using the [installation instructions](https://www.freqtrade.io/en/stable/installation/#install-code) for your OS.

Then activate the [FreqTrade shell](https://www.freqtrade.io/en/stable/installation/#activate-your-virtual-environment) and install lazyft:

```bash
# install lazyft
pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip
# initialize lazyft
lft init
```

#### FreqTrade is installed, use LazyFT in a new directory

If you have FreqTrade installed locally but want LazyFT in a fresh directory:

```bash
# Create a new directory
mkdir lft_workdir
cd lft_workdir
# Create a new virtual environment
python3 -m venv venv
# Activate the virtual environment
source venv/bin/activate.fish || source venv/bin/activate || venv/Scripts/activate
# Install freqtrade
pip install -e <FREQTRADE_PATH>/freqtrade
# Install freqtrade hyperopt deps
pip install -r <FREQTRADE_PATH>/requirements-hyperopt.txt
# Install lazyft
pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip
# Initialize lazyft
lft init
```

#### Docker

Add the following to your Dockerfile:

```docker
RUN pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip
```

### Directory

#### Config files

LFT expects FreqTrade config files in the **./configs** folder.
It will offer to create **./configs** on its first run, and it will try to detect and move existing config files there.

#### User data

LFT also expects a **./user_data** folder in the base directory and will offer to create it using FreqTrade's builtin toolset.

## Running a backtest

### Programmatic approach

```python
from lazyft.command_parameters import BacktestParameters


bp = BacktestParameters(
    config_path='config.json',
    days=90,
    download_data=True,
    max_open_trades=3,
    interval='1h',
    starting_balance=100,
    stake_amount='unlimited',
)
backtest_runner = bp.run('Strategy')
```

LFT checks for missing pair data, downloads it, then runs the backtest.

To run a backtest against the parameters from a previous hyperopt, append the hyperopt ID to the strategy name.
LFT writes that hyperopt's parameters into place before the run and cleans up afterwards, so you never edit a parameter file by hand:

```python
backtest_runner = bp.run('Strategy-1')
```

### CLI approach

You can also run backtests through the CLI:

`lft backtest run [OPTIONS] STRATEGY_NAME CONFIG INTERVAL`

Run `lft backtest run --help` for more options.

### Important things to know about backtests

#### Parameters

The **days** parameter is automatically split into 2/3rds for the hyperopt and 1/3rd for backtesting.
To bypass this, use the **timerange** parameter as you normally would in FreqTrade: `timerange='20220101-20220131'` or `timerange='20220101-'`.

The **config_path** can be a string or a [Config](https://github.com/raph92/lazyft/blob/runner/lazyft/config.py#L18) object.
It automatically searches the **configs/** directory for the named config file.

#### Post-run

The [BacktestRunner](https://github.com/raph92/lazyft/blob/runner/lazyft/backtest/runner.py#L96) class exposes a [BacktestReport](https://github.com/raph92/lazyft/blob/runner/lazyft/models/backtest.py#L76) attribute after a successful run, available as **backtest_runner.report**.

Save a run by calling **backtest_runner.save()**.
The run is logged to a database named **lazyft.db** in your working directory, and the reports are then available in aggregate through the [RepoExplorer](https://github.com/raph92/lazyft/blob/runner/lazyft/reports.py#L45).
You can access a single backtest directly through [get_backtest_repo().get(<report_id>)](https://github.com/raph92/lazyft/blob/runner/lazyft/reports.py#L454).

```python
get_backtest_repo().get(1).df()
```

|  id | strategy | hyperopt_id | date              | exchange | m_o_t | stake     | balance | n_pairlist | avg_profit_pct | avg_duration | wins | losses |  sortino |  drawdown | total_profit_pct | total_profit | trades | days | tag               |
| --: | :------- | ----------: | :---------------- | :------- | ----: | :-------- | ------: | ---------: | -------------: | :----------- | ---: | -----: | -------: | --------: | ---------------: | -----------: | -----: | ---: | :---------------- |
|   1 | Strategy |             | 06/01/22 15:32:28 | binance  |     3 | unlimited |     100 |         29 |        0.12113 | 11:52:00     |    2 |     13 | 0.545416 | 0.0251296 |           0.0053 |         0.53 |     16 |   29 | 20220503-20220601 |

### Hyperopt

The [hyperopt API](https://github.com/raph92/lazyft/blob/runner/lazyft/command_parameters.py#L208) works the same way the backtest does, with extra parameters.

### CLI approach

`lft hyperopt run [OPTIONS] STRATEGY_NAME CONFIG INTERVAL`

Run `lft hyperopt run --help` for more options.

### Programmatic approach

```python

h_params = HyperoptParameters(
    epochs=20,
    config_path='config.json',
    days=30,
    spaces="buy sell",
    loss='CalmarHyperOptLoss',
    interval='1h',
    min_trades=100,
    starting_balance=100,
    max_open_trades=3,
    stake_amount=100,
    jobs=-2,
    download_data=True,
)

h_params.run('Strategy', background=True)
report = h_params.save()

```

Passing the **background** parameter to `h_params.run()` runs the hyperopt in a separate thread, which is useful in Jupyter notebooks.

As with the backtest, the [hyperopt report](https://github.com/raph92/lazyft/blob/runner/lazyft/models/hyperopt.py#L81) is available via `h_params.report`.

#### Epochs

Access a specific epoch within the hyperopt with `h_runner.report.show_epoch(<n>)`, where **n** is the epoch number.

You can also create a new report from a specific epoch: `report.new_report_from_epoch(n)`.

Again, previous hyperopts are available through the repo:

```python
get_hyperopt_repo().df()
```

|  id | strategy  | date              | exchange | m_o_t | stake     | balance | n_pairlist | avg_profit_pct | avg_duration | wins | losses |  drawdown | total_profit_pct | total_profit | trades | days | tag                       |
| --: | :-------- | :---------------- | :------- | ----: | :-------- | ------: | ---------: | -------------: | :----------- | ---: | -----: | --------: | ---------------: | -----------: | -----: | ---: | :------------------------ |
|   1 | InverseV2 | 06/01/22 15:31:47 | binance  |     3 | unlimited |     100 |         29 |       0.704275 | 11:14:00     |    7 |     21 | 0.0351595 |        0.0711687 |         7.12 |     31 |   51 | 20220303-20220502,default |

## Custom hyperopt spaces

`SpaceHandler` lets a strategy expose optional blocks of logic that can be switched on and off from outside the strategy file.
It reads a JSON file sitting next to the strategy, named `<StrategyFile>.sh.json`, and the strategy queries it for each space:

```python
from lazyft.space_handler import SpaceHandler


class MyStrategy(IStrategy):
    sh = SpaceHandler(__file__, disable=__name__ != __qualname__)

    def populate_indicators(self, dataframe, metadata):
        if self.sh.get_space('custom_stoploss'):
            ...
```

Because the switches live in a file rather than in the strategy source, an outside script can flip them between runs.
That is what makes automated multi-stage optimization possible: enable a space, hyperopt it, save the result, disable it, move to the next one, all without touching the strategy.

To convert an existing strategy's parameters into named spaces automatically, run:

`lft sh convert <STRATEGY_NAME>`

## Remotes

Send strategies and optimized parameters to your remote servers.

### Requirements

Remotes works by sending SSH commands to your remote server.
It assumes you already have SSH keys installed there so no password prompt appears.

### Setting up remotes.json

```json
{
  "pi4": {
    "address": "pi@pi4.local",
    "path": "/home/pi/freqtrade/",
    "port": 22
  },
  "pi3": {
    "address": "pi@pi3.local",
    "path": "/home/pi/freqtrade/",
    "port": 22
  }
}
```

**More detailed explanation and changes coming soon.**

### Updating a remote strategy

```python
bot1 = remote.RemoteBot(bot_id=1, "pi3")
bot2 = remote.RemoteBot(bot_id=2, "pi4")
bot.set_strategy("Strategy1", id=<hyperopt_id>)
bot.set_strategy("Strategy2", id=<hyperopt_id>)
```

**More detailed explanation coming soon.**

## Notifications

LFT can notify you when a long hyperopt finishes, through Pushbullet or Telegram.
Set `PB_TOKEN` for Pushbullet, or `TELEGRAM_NOTIFY_TOKEN` and `TELEGRAM_NOTIFY_CHAT_ID` for Telegram.
See [notify.py](https://github.com/raph92/lazyft/blob/runner/lazyft/notify.py).

## TODO

- [ ] 95% test coverage
- [ ] Add more docs
- [ ] Import existing hyperopt and backtest data into the database from _user_data/\*\_results/_
