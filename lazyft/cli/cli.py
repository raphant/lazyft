from pathlib import Path

import typer
from freqtrade.configuration.directory_operations import create_userdata_dir

from lazyft import paths, logger
from lazyft.cli import remote, backtest, hyperopt, space_handlerify

app = typer.Typer()
app.add_typer(backtest.app, name="backtest")
app.add_typer(hyperopt.app, name="hyperopt")
app.add_typer(remote.app, name="remote")
app.add_typer(space_handlerify.app, name="sh", help='Convert strategies to SpaceHandler')


@app.command('init')
def init():
    """
    Initialize the configs and user_data folder
    """
    if not paths.CONFIG_DIR.exists():
        if input("No configs folder found. Would you like to create one? [y/n]:").lower() == "y":
            paths.CONFIG_DIR.mkdir(exist_ok=False)
        else:
            raise RuntimeError(
                "No configs folder found. Please check the current working directory."
            )
    else:
        typer.echo("Configs folder already exists")

    config_files = [str(path) for path in paths.BASE_DIR.glob("config*.json")]
    if not any(config_files):
        typer.echo(
            "No config files found. Please copy existing config files to the configs "
            "folder or create a new one using `freqtrade new-config`."
        )
    else:
        if (
            input(
                f"Found config files in the base directory. LazyFT only uses files"
                ' in the "configs" folder. Would you like me to move them to the "configs"'
                " folder? [y/n]:"
            ).lower()
            == "y"
        ):
            for path in config_files:
                Path(path).rename(paths.CONFIG_DIR / Path(path).name)
                typer.echo(f"Moved {path} to {paths.CONFIG_DIR / Path(path).name}")

    if not paths.USER_DATA_DIR.exists():
        if (
            input("No user_data folder found. Would you like me to create one? [y/n]:").lower()
            == "y"
        ):
            create_userdata_dir(paths.USER_DATA_DIR, create_dir=True)
        else:
            typer.echo("Continuing with no user_data folder")
    else:
        typer.echo("User_data folder already exists")
    typer.echo("Done")


def main():
    app()


if __name__ == '__main__':
    main()
