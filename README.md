# LazyFT

> **Status:** this project is no longer actively maintained.

LazyFT is a wrapper around [FreqTrade](https://github.com/freqtrade/freqtrade) for people who spend a lot of time backtesting, hyperopting, and iterating on strategies locally. It adds a small workflow layer on top of FreqTrade so you can run experiments faster, keep track of results, and reuse past runs more easily.

## What LazyFT helps with

- Automatically download missing market data before backtests and hyperopts
- Save and browse historical backtest and hyperopt runs
- Reuse hyperopt parameter sets by ID when launching backtests
- Version strategy files alongside optimization results
- Inspect pairlists and config values from earlier runs
- Run common workflows through a simple `lft` CLI
- Convert strategies to use `SpaceHandler`-based optimization groups
- Push strategy updates to remote bots over SSH

## Best fit

LazyFT was built around a Linux, non-Docker FreqTrade setup. If your workflow is similar, setup is usually straightforward. Docker-based setups may need extra adaptation.

If you run into gaps, open an issue and document your environment so other users can benefit too.

## Requirements

- Python environment with FreqTrade installed
- FreqTrade hyperopt dependencies available
- A local working directory for configs, user data, logs, and results

LazyFT expects to run from your working directory and uses that directory as its base path.

## Installation

### Recommended: install inside an existing FreqTrade environment

Follow the official [FreqTrade installation guide](https://www.freqtrade.io/en/stable/installation/#install-code) for your platform, activate that environment, then install LazyFT:

```bash
pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip
lft init
```

### Alternative: use LazyFT from a fresh working directory

```bash
mkdir lft_workdir
cd lft_workdir
python3 -m venv venv
source venv/bin/activate.fish || source venv/bin/activate || . venv/Scripts/activate
pip install -e <FREQTRADE_PATH>/freqtrade
pip install -r <FREQTRADE_PATH>/requirements-hyperopt.txt
pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip
lft init
```

### Docker note

LazyFT can be installed in a container image:

```dockerfile
RUN pip install https://github.com/raph92/lazyft/archive/refs/heads/runner.zip
```

But the project was not primarily designed around Docker workflows, so expect some manual setup.

## Expected project layout

After `lft init`, the working directory should look roughly like this:

```text
.
├── configs/
├── logs/
└── user_data/
    ├── strategies/
    ├── data/
    ├── backtest_results/
    └── hyperopt_results/
```

Important conventions:

- Config files live in `./configs`
- FreqTrade user data lives in `./user_data`
- LazyFT stores logs in `./logs`
- Saved run metadata is stored in `lazyft.db` in the working directory

## Quick start

### 1. Initialize the workspace

```bash
lft init
```

This command helps create:

- `configs/`
- `user_data/`
- moved `config*.json` files from the base directory into `configs/`

### 2. Run a backtest

```bash
lft backtest run MyStrategy config.json 1h --days 90
```

Useful variants:

- `lft backtest show <id>`
- `lft backtest show <id> --type D`
- `lft backtest from-hyperopt <hyperopt-id>`
- `lft backtest export-trades <backtest-id>`

### 3. Review past hyperopts

```bash
lft hyperopt list
lft hyperopt show 12 --params
```

### 4. Run a hyperopt from an earlier backtest

```bash
lft hyperopt run-on-backtest 5 config.json --epochs 100 --spaces "buy sell"
```

## CLI overview

The main entrypoint is:

```bash
lft --help
```

Current command groups include:

- `lft init`
- `lft backtest ...`
- `lft hyperopt ...`
- `lft remote ...`
- `lft sh ...`

### Backtest commands

- `lft backtest run`
- `lft backtest show`
- `lft backtest from-hyperopt`
- `lft backtest export-trades`

### Hyperopt commands

- `lft hyperopt list`
- `lft hyperopt show`
- `lft hyperopt run-on-backtest`

### Remote commands

- `lft remote update-strategy`

### SpaceHandler helper

- `lft sh convert`

This converts a strategy to use `SpaceHandler`-controlled optimization groups.

## Python API examples

### Backtest

```python
from lazyft.command_parameters import BacktestParameters

params = BacktestParameters(
    config_path="config.json",
    days=90,
    download_data=True,
    max_open_trades=3,
    interval="1h",
    starting_balance=100,
    stake_amount="unlimited",
)

runner = params.run("MyStrategy")
runner.save()
```

### Hyperopt

```python
from lazyft.command_parameters import HyperoptParameters

params = HyperoptParameters(
    epochs=20,
    config_path="config.json",
    days=30,
    spaces="buy sell",
    loss="CalmarHyperOptLoss",
    interval="1h",
    min_trades=100,
    starting_balance=100,
    max_open_trades=3,
    stake_amount=100,
    jobs=-2,
    download_data=True,
)

runner = params.run("MyStrategy")
report = runner.report
```

## How result tracking works

When you save a completed run, LazyFT stores metadata so you can later:

- view aggregate history for a strategy
- inspect pair performance across saved runs
- compare results across date ranges
- reuse parameter IDs from earlier hyperopts

This is one of the main benefits of the project over running isolated FreqTrade commands manually.

## Remote bot support

LazyFT includes basic remote deployment helpers that assume:

- SSH access is already configured
- keys are installed on the target host
- each remote has a known path to its FreqTrade instance

Example `remotes.json`:

```json
{
  "pi4": {
    "address": "pi@pi4.local",
    "path": "/home/pi/freqtrade/",
    "port": 22
  }
}
```

## Examples and docs

- Notebook examples: `./examples`
- Sphinx docs source: `./docs/source`
- Repository root notebook: `./backtest_and_hyperopt_example.ipynb`

## Limitations

- Not actively maintained
- Best suited to local Linux workflows
- Docker support is limited
- Documentation is still incomplete in several areas

## Development

There is a `tests/` directory in the repository, but in this environment `pytest` was not installed, so the test suite could not be run before this documentation update.

## License

GPLv3
