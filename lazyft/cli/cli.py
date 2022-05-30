import typer

from lazyft.cli import remote, backtest, hyperopt, space_handlerify

app = typer.Typer()
app.add_typer(backtest.app, name="backtest")
app.add_typer(hyperopt.app, name="hyperopt")
app.add_typer(remote.app, name="remote")
app.add_typer(space_handlerify.app, name="sh", help='Convert strategies to SpaceHandler')


def main():
    app()


if __name__ == '__main__':
    main()
