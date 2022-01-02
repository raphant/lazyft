"""
A rest API for LazyFt built with FastAPI
"""
from queue import Queue, Empty
from threading import Thread

from fastapi import FastAPI

import lft_rest.backtest
from lft_rest import worker, State, Settings, hyperopt, logger
from lft_rest.models import BacktestInput, HyperoptInput

app = FastAPI()

work_queue = Queue()


@app.get("/")
def root():
    return {"message": "Pong"}


def _backtest_pair(pair, strategy, days, exchange, timeframe, min_avg_profit, min_trades):
    bt = lft_rest.backtest.get_backtest(pair, strategy, days)
    if not bt:
        backtest_input = BacktestInput(
            pair=pair.upper(),
            strategy=strategy,
            exchange=exchange,
            days=days,
            timeframe=timeframe,
        )
        if (
            backtest_input not in State.backtest_queue.queue
            and backtest_input not in State.current_backtests
        ):
            State.backtest_queue.put_nowait(backtest_input)
            return {'status': 'queued'}
        return {'status': 'pending'}
    return {
        'status': bt.is_valid(min_avg_profit, min_trades),
        'info': {'trades': bt.trades, 'wins': bt.wins, 'losses': bt.losses, 'ratio': bt.ratio},
    }


@app.get('/pair/backtest')
async def backtest_pair(
    pairs: str,
    strategy: str,
    timeframe: str = '5m',
    exchange: str = 'kucoin',
    min_avg_profit: float = Settings.min_ratio,
    min_trades: int = 3,
    days: int = 7,
):
    pairs = [p for p in pairs.split(',') if p]
    results = {}
    for pair in pairs:
        results[pair] = _backtest_pair(
            pair, strategy, days, exchange, timeframe, min_avg_profit, min_trades
        )
    return results


def _hyperopt_pair(pair, strategy, days, timeframe, exchange, min_avg_profit, min_trades, epochs):
    hopt = hyperopt.get_hyperopt(pair, strategy, days)
    if not hopt:
        hyperopt_input = HyperoptInput(
            pair=pair.upper(),
            strategy=strategy,
            exchange=exchange,
            days=days,
            epochs=epochs,
            timeframe=timeframe,
            min_trades=min_trades,
        )
        if (
            hyperopt_input not in State.hyperopt_queue.queue
            and State.current_hyperopt != hyperopt_input
        ):
            State.hyperopt_queue.put_nowait(hyperopt_input)
            return {'status': 'queued'}
        return {'status': 'pending'}
    valid = hopt.is_valid(min_avg_profit, min_trades)
    return {
        'status': valid,
        'info': {
            'trades': hopt.trades,
            'wins': hopt.wins,
            'losses': hopt.losses,
            'ratio': hopt.ratio,
            'params': hopt.params if valid else {},
        },
    }


@app.get('/pair/hyperopt')
def hyperopt_pair(
    pairs: str,
    strategy: str,
    timeframe: str = '5m',
    exchange: str = 'kucoin',
    min_avg_profit: float = Settings.min_ratio,
    min_trades: int = 3,
    days: int = 7,
    epochs: int = 50,
):
    pairs = [p for p in pairs.split(',') if p]
    results = {}
    for pair in pairs:
        results[pair] = _hyperopt_pair(
            pair, strategy, days, timeframe, exchange, min_avg_profit, min_trades, epochs
        )
    return results


@app.get('/shutdown')
def shutdown():
    logger.info('Client requested shutdown... clearing queues.')
    while any(State.hyperopt_queue.queue) or any(State.backtest_queue.queue):
        try:
            State.hyperopt_queue.get_nowait()
        except Empty:
            continue
        try:
            State.backtest_queue.get_nowait()
        except Empty:
            continue
    return {'status': 'ok'}


for i in range(Settings.n_backtest_workers):
    Thread(target=worker.backtest_worker, daemon=True).start()
Thread(target=worker.hyperopt_worker, daemon=True).start()

lft_rest.backtest.clean_backtests()
