from __future__ import annotations

from sqlmodel import SQLModel

from lazyft.database import engine

from .backtest import BacktestPerformance, BacktestReport
from .base import PerformanceBase, ReportBase
from .hyperopt import HyperoptPerformance, HyperoptReport
from .strategy import StrategyBackup

SQLModel.metadata.create_all(engine)


all = [
    BacktestPerformance,
    BacktestReport,
    HyperoptPerformance,
    HyperoptReport,
    PerformanceBase,
    ReportBase,
    StrategyBackup,
]
