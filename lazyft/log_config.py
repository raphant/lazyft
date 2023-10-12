import sys

from loguru import logger

from lazyft import paths


def non_exec_only(record):
    return "type" not in record["extra"]


def filter_log_file(record, log_type: str):
    return "type" in record["extra"] and record["extra"]["type"] == log_type


def setup_logger():
    logger.configure(
        handlers=[
            dict(
                sink=sys.stdout,
                level="INFO",
                backtrace=False,
                diagnose=False,
                enqueue=False,
                filter=non_exec_only,
            ),
            dict(
                sink=paths.LOG_DIR.joinpath("logs.log"),
                backtrace=True,
                diagnose=True,
                level="DEBUG",
                delay=True,
                enqueue=True,
                filter=non_exec_only,
                retention="5 days",
                rotation="1 MB",
            ),
            dict(
                sink=paths.LOG_DIR.joinpath("hyperopt.log"),
                retention="5 days",
                rotation="2.5 MB",
                format="{message}",
                filter=lambda r: filter_log_file(r, log_type="hyperopt"),
                enqueue=True,
            ),
            dict(
                sink=paths.LOG_DIR.joinpath("backtest.log"),
                retention="5 days",
                rotation="2.5 MB",
                format="{message}",
                filter=lambda r: filter_log_file(r, log_type="backtest"),
                enqueue=True,
            ),
            dict(
                sink=paths.LOG_DIR.joinpath("general_exec.log"),
                retention="5 days",
                rotation="1 MB",
                format="{message}",
                filter=lambda r: filter_log_file(r, log_type="general"),
                enqueue=True,
            ),
        ]
    )
    return logger
