from typing import Optional

import rapidjson
from loguru import logger
from sqlmodel import Session, select

import lazyft.command
from lazyft import hyperopt, backtest, downloader
from lazyft.backtest.runner import BacktestRunner
from lazyft.command_parameters import HyperoptParameters, BacktestParameters
from lazyft.hyperopt.runner import HyperoptRunner
from lazyft.models import HyperoptReport, BacktestReport
from lft_rest import State, Settings
from lft_rest.errors import HyperoptError, MaxAttemptError, BacktestError
from lft_rest.models import engine, HyperoptResult, HyperoptInput
from lft_rest.util import get_config


def save_hyperopt_result(
    bt_report: BacktestReport, hopt_input: HyperoptInput, hyperopt_report: HyperoptReport = None
) -> None:
    logger.info(
        f"Saving Hyperopt results for {hopt_input.pair} {hopt_input.strategy} {hopt_input.days}"
    )
    if not bt_report or not hyperopt_report:
        HyperoptResult(
            pair=hopt_input.pair,
            strategy=hopt_input.strategy,
            days=hopt_input.days,
            ratio=0.0,
            wins=0,
            losses=0,
            trades=0,
            params_json='{}',
        ).save()
        return
    HyperoptResult(
        pair=hopt_input.pair,
        strategy=hopt_input.strategy,
        days=hopt_input.days,
        ratio=bt_report.performance.profit_ratio,
        wins=bt_report.performance.wins,
        losses=bt_report.performance.losses,
        trades=bt_report.performance.trades,
        params_json=rapidjson.dumps(hyperopt_report.parameters),
    ).save()


def execute_hyperopt(hyperopt_inputs: HyperoptInput) -> Optional[HyperoptReport]:
    if State.failed_hyperopts[hyperopt_inputs.pair] >= Settings.max_backtest_attempts:
        raise MaxAttemptError(
            f"Hyperopt failed too many times for {hyperopt_inputs.pair} {hyperopt_inputs.strategy} "
            f"{hyperopt_inputs.days}"
        )
    # timerange = get_timerange(hyperopt_inputs.days)
    config = get_config(hyperopt_inputs.exchange)
    params = HyperoptParameters(
        epochs=hyperopt_inputs.epochs,
        # timerange=timerange,
        days=hyperopt_inputs.days,
        strategies=[hyperopt_inputs.strategy],
        interval=hyperopt_inputs.timeframe,
        config_path=str(config),
        pairs=[hyperopt_inputs.pair],
        stake_amount="unlimited",
        spaces='default',
        starting_balance=100,
        max_open_trades=1,
        min_trades=hyperopt_inputs.min_trades,
        loss='ROIAndProfitHyperOptLoss',
        jobs=-2,
        download_data=True,
        tag=f'{hyperopt_inputs.pair}',
    )
    logger.info(
        f'Hyperopting {hyperopt_inputs.pair} {hyperopt_inputs.strategy} for {params.days}'
        f' days ({State.failed_backtest[hyperopt_inputs.pair] + 1} attempt(s))'
    )
    params.tag += f'_{hyperopt_inputs.timeframe}'
    commands = lazyft.command.create_commands(
        params,
        verbose=False,
    )
    runner = HyperoptRunner(commands[0], notify=False)
    runner.execute(background=True)
    runner.join()
    if runner.exception:
        if str(runner.exception) == "No data found. Terminating.":
            downloader.remove_pair_record(hyperopt_inputs.pair, runner.strategy, params)
        else:
            logger.error('\n'.join(runner.output_list[-100:]))
        State.failed_hyperopts[hyperopt_inputs.pair] += 1
        raise HyperoptError(f'Failed to hyperopt {hyperopt_inputs.pair}')
    try:
        save = runner.save()
        logger.success(f'Hyperopt for {hyperopt_inputs.pair} completed: {save.performance.dict()}')
        return save
    except ValueError:
        State.failed_hyperopts[hyperopt_inputs.pair] += 1
        return None


def execute_hyperopt_backtest(report: HyperoptReport) -> Optional[BacktestReport]:
    if not report:
        return None

    config = get_config(report.exchange)
    params = BacktestParameters(
        # timerange=get_timerange(report.performance.days),
        days=report.performance.days,
        strategies=[f'{report.strategy}-{report.id}'],
        starting_balance=report.starting_balance,
        interval=report.timeframe,
        config_path=str(config),
        pairs=report.pairlist,
        stake_amount=report.stake_amount,
        max_open_trades=1,
        tag=f'{report.pairlist[0]}_hbt',
    )
    logger.info(
        f'Backtesting {report.pairlist[0]} {report.strategy} for {params.days}'
        f' days ({State.failed_backtest[report.pairlist[0]] + 1} attempt(s))'
    )
    params.tag += f'_{report.timeframe}'
    commands = backtest.create_commands(
        params,
        verbose=False,
    )
    runner = BacktestRunner(commands[0])
    runner.execute()
    if runner.exception:
        # State.failed_backtest[report.pairlist[0]] += 1
        raise BacktestError(f'Failed to backtest {report.pairlist[0]}') from runner.exception
    try:
        return runner.save()
    except ValueError:
        return None


def get_hyperopt(pair, strategy, days) -> Optional[HyperoptResult]:
    with Session(engine) as session:
        statement = select(HyperoptResult)
        results = session.exec(statement).fetchall()
        filter = [
            r
            for r in results
            if r.pair == pair and r.strategy == strategy and r.days == days and r.valid_date
        ]
        if any(filter):
            return filter[0]


def get_valid_hyperopts() -> list[tuple[str, str, int]]:
    """
    :return: a list of Pair, Strategy, Days tuples for which a Hyperopt has been run
    """
    with Session(engine) as session:
        statement = select(HyperoptResult)
        results = session.exec(statement)
        return [(r.pair, r.strategy, r.days) for r in results.fetchall() if r.valid_date]


def clean_hyperopts():
    """
    Remove any Hyperopt that has an invalid date
    """
    with Session(engine) as session:
        statement = select(HyperoptResult)
        results = session.exec(statement)
        for r in results.fetchall():
            if not r.valid_date:
                logger.info(f"Removing Hyperopt {r.pair} {r.strategy} {r.days}")
                session.delete(r)
        session.commit()
