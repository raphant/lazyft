import os
import pathlib

from easyft.strategy import Strategy, constants


def test_strategy_id_lookup():
    strategy = Strategy(
        'binh', 'temp', save_dir=pathlib.Path(__file__).parent.resolve()
    )
    path = strategy.create_strategy()
    assert path.exists()
    path.unlink()
    path.parent.rmdir()
