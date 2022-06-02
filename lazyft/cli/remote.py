from typing import Optional

import typer

from lazyft.remote import RemoteBot

app = typer.Typer()


@app.command()
def update_strategy(
    bot_id: int = typer.Argument(...),
    strategy_name: str = typer.Argument(..., help="Name of the strategy"),
    hyperopt_id: Optional[str] = typer.Option(None, "-h", "--hyperopt-id", help="Hyperopt ID"),
    restart: bool = typer.Option(False, "-r", "--restart", help="Restart the bot"),
):
    """Update the strategy of a remote bot"""
    bot = RemoteBot(bot_id, "pi")
    bot.set_strategy(strategy_name, id=hyperopt_id)
    if restart:
        bot.restart()
