import typer
from rich import console, pretty, traceback
from easyft import backtest, hyperopt, confirm

traceback.install()
pretty.install()


def get_final_output(result: tuple):
    params = result[2]
    bs = params.pop('params')
    buy_params = {k: v for k, v in bs.items() if 'buy' in k}
    sell_params = {k: v for k, v in bs.items() if 'sell' in k}

    dictionary = dict(**params)
    if buy_params:
        dictionary['buy_params'] = buy_params
    if sell_params:
        dictionary['sell_params'] = sell_params

    return dictionary


print = console.Console().print


def study():
    from easyft import hyperopt

    typer.run(hyperopt.new_hyperopt_cli)


def backtest_cli():
    typer.run(backtest.new_backtest)


if __name__ == '__main__':
    study()
