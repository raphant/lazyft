# LazyFT

LazyFT is convenient [FreqTrade](https://github.com/freqtrade/freqtrade) wrapper that makes developing and testing strategies a lot easier for me. My hope is that it will do the same for you.

The features include but are not limited to:

- **Automatic data downloading** - LFT will always know when you need to download data for your pairs before hyperopting or backtesting, so no more worrying about that.
- **Backtest and Hyperopt Repository** - LFT keeps track of every hyperopt and backtest you save so that allows you to:
  - View the overall performance of a strategies' backtest/hyperopt history
  - View the performance of a pair throughout all of your backtest/hyperopt history
  - Get the performance from all of your strategies from a specific date range.
  - and more!
- **Hyperopt IDs** - LFT will automatically remove and add the appropriate parameters based on the IDs you pass to a backtest. No more manually deleting and re-adding parameter files.
- **Smart Space Handling** - LFT supports creating custom spaces for strategies, and that extends what is possible with hyperopting.
- **Automated Hyperopting and Bactesting** - With the ability of SpaceHandler you can automate the process of hyperopting and backtesting by automatically enabling and disabling custom spaces in a Strategy.
- **Strategy versioning** - LFT will automatically save a copy of the your strategy after a hyperopt that you can easily retrieve even after you've made changes to your strategy.
- Easily access pairlist and other config settings from previous runs.
- Get notifications when your hyperopt is completed.
- and more!

## Getting Stated

### Caution

**Please Read**

Initially, I did not plan on releasing this publicly and so I designed LazyFT with my only setup in mind.

My main setup is Manjaro Arch and all of my dry-run/live bots run on Ubuntu with ssh-keys setup. My main FreqTrade environment is not setup using Docker, thus you may have some difficulties setting up LazyFT if you use Docker to run backtests and hyperopts.

If your setup is similar to mine (linux & non-Docker FreqTrade), getting started should be simple.

That being said, I do plan on adding support for other setups and so please feel free to [open an issue](https://github.com/raph92/lazyft/issues/new) if you have any questions/requests.

### Installation

#### Install in a FreqTrade environment (Recommended)

If you haven't already, git clone a FreqTrade enviroment using the [installation instructuctions](https://www.freqtrade.io/en/stable/installation/#install-code) for your OS.

Afterwards, make sure you have the [Freqtrade shell activated](https://www.freqtrade.io/en/stable/installation/#activate-your-virtual-environment), then install lazyft:

```bash
# install lazyft
pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip
# initialize lazyft
lft init
```

#### FreqTrade is installed, use LazyFT in a new directory

If you have FreqTrade installed locally, but want to install LazyFT in a fresh directory, then you can use the following commands:

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

#### Config Files

LFT expects FreqTrade config files to be in the **./configs** folder. It will ask to automatically create **./config** on it's first run. It will also attempt to detect and automatically move all config files to the **./configs** folder.

#### User Data

LFT also expects a **./user_data** folder in the base directory and will offer to create it using FreqTrade's builtin toolset.

## Running a Backtest

### Programatic Approach

Programatically, you can run a backtest using the following:

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

Now, LFT will check to see if any pair data is missing and then proceed to run the backtest.

### CLI Approach

You can also run backtests through the CLI:

`lft backtest run [OPTIONS] STRATEGY_NAME CONFIG INTERVAL`

Run `lft backtest run --help` for more options

### Important Things to Know About Backtests

#### Parameters

The **days** parameter will automatically be split into 2/3rds for the hyperopt and 1/3rd for backtesting.
To bypass this you can use the **timerange** parameter like you normally would in freqtrade: `timerange='20220101-20220131'` or `timerange='20220101-'`.

The **config_path** can be a string or a [Config](https://github.com/raph92/lazyft/blob/runner/lazyft/config.py#L18) object. It will automatically search the **configs/** directory for the specified config file.

#### Post-run

The [BacktestRunner](https://github.com/raph92/lazyft/blob/runner/lazyft/backtest/runner.py#L96) class will have a [BacktestReport](https://github.com/raph92/lazyft/blob/runner/lazyft/models/backtest.py#L76) attribute that can will be available after a successful run. This can be accessed by **backtest_runner.report**.

You can save a run by calling **backtest_runner.save()** and the run will be logged to the database named **lazyft.db** in your working directory. The reports can then by accessed in aggregate using the [RepoExplorer](https://github.com/raph92/lazyft/blob/runner/lazyft/reports.py#L45). You can directly access all backtest through [get_backtest_repo().get(<report_id>)](https://github.com/raph92/lazyft/blob/runner/lazyft/reports.py#L454).

```python
get_backtest_repo().get(1).df()
```

|  id | strategy | hyperopt_id | date              | exchange | m_o_t | stake     | balance | n_pairlist | avg_profit_pct | avg_duration | wins | losses |  sortino |  drawdown | total_profit_pct | total_profit | trades | days | tag               |
| --: | :------- | ----------: | :---------------- | :------- | ----: | :-------- | ------: | ---------: | -------------: | :----------- | ---: | -----: | -------: | --------: | ---------------: | -----------: | -----: | ---: | :---------------- |
|   1 | Strategy |             | 06/01/22 15:32:28 | binance  |     3 | unlimited |     100 |         29 |        0.12113 | 11:52:00     |    2 |     13 | 0.545416 | 0.0251296 |           0.0053 |         0.53 |     16 |   29 | 20220503-20220601 |

### Hyperopt

The [hyperopt API](https://github.com/raph92/lazyft/blob/runner/lazyft/command_parameters.py#L208) works the same way the Backtest does except that it has extra parameters.

### CLI Approach

`lft hyperopt run [OPTIONS] STRATEGY_NAME CONFIG INTERVAL`

Run `lft hyperopt run --help` for more options

### Programatic Approach

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

Passing the **background** parameter to `h_params.run()` will allow the hyperopt to run in a separate thread. This is useful when running in jupyter notebooks.

Similar to the backtest, you can access the [hyperopt report](https://github.com/raph92/lazyft/blob/runner/lazyft/models/hyperopt.py#L81) via `h_params.report`.

#### Epochs

You can access a specific epoch within the hyperopt as follows:
`h_runner.report.show_epoch(<n>)`, **n** being the epoch number to show.

You can also quickly create a new report from the specific epoch: `report.new_report_from_epoch(n)`

Again, you can access previous hyperopts through the repo:

```python
get_hyperopt_repo().df()
```

|  id | strategy  | date              | exchange | m_o_t | stake     | balance | n_pairlist | avg_profit_pct | avg_duration | wins | losses |  drawdown | total_profit_pct | total_profit | trades | days | tag                       |
| --: | :-------- | :---------------- | :------- | ----: | :-------- | ------: | ---------: | -------------: | :----------- | ---: | -----: | --------: | ---------------: | -----------: | -----: | ---: | :------------------------ |
|   1 | InverseV2 | 06/01/22 15:31:47 | binance  |     3 | unlimited |     100 |         29 |       0.704275 | 11:14:00     |    7 |     21 | 0.0351595 |        0.0711687 |         7.12 |     31 |   51 | 20220303-20220502,default |

## Remotes

Easily send strategies and optimized parameters to your remote servers.

### Requirements

Remotes relies on sending SSH commands to your remote server. It also assumes that you have ssh keys already installed on the server to bypass typing in a password.

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

**More Detailed Explanation and Changes Coming Soon**

### Updating a Remote Strategy

```python
bot1 = remote.RemoteBot(bot_id=1, "pi3")
bot2 = remote.RemoteBot(bot_id=2, "pi4")
bot.set_strategy("Strategy1", id=<hyperopt_id>)
bot.set_strategy("Strategy2", id=<hyperopt_id>)
```

**More Detailed Explanation Coming Soon**

## TODO

- [ ] 95% Test Coverage
- [ ] Add more docs
- [ ] Import existing hyperopt and backtest data into the database from user_data/\*\_results/
