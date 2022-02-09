from tenacity import retry

import lft_rest.backtest
from lazyft import notify
from lft_rest import State, logger, hyperopt
from lft_rest.backtest import execute_backtest
from lft_rest.errors import BacktestError, HyperoptError, MaxAttemptError
from lft_rest.models import BacktestInput, HyperoptInput, BacktestResult, HyperoptResult


@retry(reraise=True)
def backtest_worker():
    logger.info("BacktestWorker started")
    while True:
        bt_input: BacktestInput = State.backtest_queue.get()
        logger.info(f"BacktestWorker got {bt_input}")
        State.current_backtests.append(bt_input)
        try:
            if (
                bt_input.pair,
                bt_input.strategy,
                bt_input.days,
            ) in lft_rest.backtest.get_valid_backtests():
                logger.debug(f'Skipping backtest {bt_input.pair} {bt_input.strategy}')
                continue
            try:
                report = execute_backtest(bt_input)
            except BacktestError as e:
                logger.exception(e)
                continue
            except MaxAttemptError:
                logger.exception(f"Max attempts reached for {bt_input.pair} {bt_input.strategy}")
                BacktestResult.null(bt_input).save()
                continue
            except Exception as e:
                logger.exception(f'Failed to execute backtest for {bt_input.pair}', e)
                notify.notify_telegram(
                    f'Lft_rest - Failed to execute backtest for {bt_input.pair}', f'{type(e)}: {e}'
                )
                continue
            try:
                lft_rest.backtest.save_backtest_results(report, bt_input)
            except Exception as e:
                logger.exception(f'Failed to save backtest results for {bt_input.pair}', e)
        finally:
            State.current_backtests.remove(bt_input)
            logger.info(f'{len(State.backtest_queue.queue)} backtest(s) in progress')


@retry
def hyperopt_worker():
    logger.info("HyperoptWorker started")
    while True:
        hopt_input: HyperoptInput = State.hyperopt_queue.get()
        State.current_hyperopt = hopt_input

        try:
            if (
                hopt_input.pair,
                hopt_input.strategy,
                hopt_input.days,
            ) in hyperopt.get_valid_hyperopts():
                logger.debug(f'Skipping hyperopt {hopt_input.pair} {hopt_input.strategy}')
                continue
            try:
                report = hyperopt.execute_hyperopt(hopt_input)
            except HyperoptError as e:
                logger.exception(e)
                continue
            except MaxAttemptError:
                logger.exception(
                    f"Max attempts reached for {hopt_input.pair} {hopt_input.strategy}"
                )
                HyperoptResult.null(hopt_input).save()
                continue
            try:
                bt_report = hyperopt.execute_hyperopt_backtest(report)
                hyperopt.save_hyperopt_result(bt_report, hopt_input, report)
            except Exception as e:
                logger.exception(f'Failed to save hyperopt results for {hopt_input.pair}', e)
        finally:
            State.current_hyperopt = None
            logger.info(f'{len(State.hyperopt_queue.queue)} hyperopt(s) in progress')
