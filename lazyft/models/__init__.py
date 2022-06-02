from __future__ import annotations

from sqlmodel import SQLModel

from lazyft.database import engine

from .base import PerformanceBase, ReportBase
from .backtest import BacktestPerformance, BacktestReport
from .hyperopt import HyperoptPerformance, HyperoptReport
from .strategy import StrategyBackup

SQLModel.metadata.create_all(engine)


__all__ = [
    "ReportBase",
    "PerformanceBase",
    "BacktestPerformance",
    "BacktestReport",
    "HyperoptPerformance",
    "HyperoptReport",
    "StrategyBackup",
]
