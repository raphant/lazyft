from __future__ import annotations

from sqlmodel import SQLModel

from lazyft.database import engine

from .base import ReportBase, PerformanceBase
from .strategy import StrategyBackup
from .backtest import BacktestReport, BacktestPerformance
from .hyperopt import HyperoptReport, HyperoptPerformance

SQLModel.metadata.create_all(engine)
