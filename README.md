# lazyft

A convenient FreqTrade wrapper-library that makes it easy to develop strategies

## Getting Stated

### Installation

#### Install in existing FreqTrade environment

`pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip`

#### Quick start in new environment

```bash
git clone https://github.com/raph92/lazyft.git
cd lazyft
pip install -e .
lft init
```

### What You Need

#### Config Files

LazyFT (LFT) expects FreqTrade config files to be in the **./configs** folder. It will ask to automatically create **./config** on it's first run. It will also attempt to detect and automatically move all config files to the **./configs** folder.

#### User Data

LFT also expects a **./user_data** folder in the base directory.

## Running

### Backtest

```python
bp = BacktestParameters(
    config_path='config.json',
    days=365,
    download_data=True,
    max_open_trades=3,
    interval='1h',
    starting_balance=100,
    stake_amount='unlimited',
)
backtest_runner = bp.run('Strategy')
```

#### Important Things to Know About Backtests

The **days** parameter will automatically be split into 2/3rds for the hyperopt and 1/3rd for backtesting.

To bypass this you can use the **timerange** parameter like you normally would in freqtrade: `20220101-20220131` or `20220101-`.

The **config_path** will can be a string or a **lazyft.config.Config** object. It will automatically search the **configs/** directory.

The [BacktestRunner](https://github.com/raph92/lazyft/blob/runner/lazyft/backtest/runner.py#L95) class will have a [BacktestReport](https://github.com/raph92/lazyft/blob/runner/lazyft/models/backtest.py#L75) attribute that will be saved after a successful run. This can be accessed by **backtest_runner.report**.

You can save a run by calling **backtest_runner.save()** and the run will be logged to the database **lazyft.db** in your working directory. The reports can then by accessed in aggregate using the [RepoExplorer](https://github.com/raph92/lazyft/blob/runner/lazyft/reports.py#L45). You can directly access all backtest through [get_backtest_repo().get(<report_id>)](https://github.com/raph92/lazyft/blob/runner/lazyft/reports.py#L454).
