from typing import Optional

from loguru import logger
from sqlmodel import Session, select

from lazyft import downloader
from lazyft.backtest.runner import BacktestRunner
from lazyft.command import create_commands
from lazyft.command_parameters import BacktestParameters
from lazyft.models import BacktestReport
from lft_rest import State, Settings
from lft_rest.errors import BacktestError, MaxAttemptError
from lft_rest.models import BacktestResult, engine, BacktestInput
from lft_rest.util import get_timerange, get_config


def save_backtest_results(report: BacktestReport, parameters: BacktestInput):
    logger.info(
        f"Saving backtest results for {parameters.pair} {parameters.strategy} {parameters.days}"
    )
    BacktestResult(
        pair=parameters.pair,
        exchange=report.exchange,
        strategy=parameters.strategy,
        ratio=report.performance.profit_ratio,
        wins=report.performance.wins,
        losses=report.performance.losses,
        days=parameters.days,
        trades=report.performance.trades,
    ).save()


def get_backtest(pair, strategy, days) -> Optional[BacktestResult]:
    with Session(engine) as session:
        statement = select(BacktestResult)
        results = session.exec(statement)
        filter = [
            r
            for r in results.fetchall()
            if r.pair == pair and r.strategy == strategy and r.days == days and r.valid_date
        ]
        if any(filter):
            return filter[0]


def get_valid_backtests() -> list[tuple[str, str, int]]:
    """
    :return: a list of Pair, Strategy, Days tuples for which a backtest has been run
    """
    with Session(engine) as session:
        statement = select(BacktestResult)
        results = session.exec(statement)
        return [(r.pair, r.strategy, r.days) for r in results.fetchall() if r.valid_date]


def clean_backtests():
    """
    Remove any backtest that has an invalid date
    """
    with Session(engine) as session:
        statement = select(BacktestResult)
        results = session.exec(statement)
        for r in results.fetchall():
            if not r.valid_date:
                logger.info(f"Removing backtest {r.pair} {r.strategy} {r.days}")
                session.delete(r)
        session.commit()


def execute_backtest(backtest_input: BacktestInput) -> BacktestReport:
    if State.failed_backtest[backtest_input.pair] >= Settings.max_backtest_attempts:
        raise MaxAttemptError(
            f"Backtest failed too many times for {backtest_input.pair} {backtest_input.strategy} {backtest_input.days}"
        )
    logger.info(
        f'Backtesting {backtest_input.pair} {backtest_input.strategy} for {backtest_input.days} '
        f'days ({State.failed_backtest[backtest_input.pair] + 1} attempt(s))'
    )
    timerange = get_timerange(backtest_input.days)
    config = get_config(backtest_input.exchange)
    b_params = BacktestParameters(
        timerange=timerange,
        strategies=[backtest_input.strategy],
        interval=backtest_input.timeframe,
        config_path=str(config),
        pairs=[backtest_input.pair],
        stake_amount="unlimited",
        starting_balance=100,
        max_open_trades=1,
        download_data=True,
        tag=f'{backtest_input.pair}-{timerange}',
    )
    commands = create_commands(
        b_params,
        verbose=False,
    )
    b_runner = BacktestRunner(commands[0])
    b_runner.execute()
    if b_runner.exception:
        if str(b_runner.exception) == "No data found. Terminating.":
            downloader.remove_pair_record(backtest_input.pair, b_runner.strategy, b_params)
        else:
            logger.error('\n'.join(b_runner.output_list[-100:]))
        State.failed_backtest[backtest_input.pair] += 1
        raise BacktestError(f'Failed to backtest {backtest_input.pair}') from b_runner.exception
    save = b_runner.save()
    logger.success(f"Backtest saved: {save.performance.dict()}")
    return save
