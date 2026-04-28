from __future__ import annotations

from pathlib import Path
import sys

from loguru import logger


_CONFIGURED = False


def configure_logging(run_name: str, artifact_dir: Path) -> Path:
    """配置终端和文件日志输出。"""
    global _CONFIGURED

    log_dir = artifact_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{run_name}.log"

    if not _CONFIGURED:
        logger.remove()
        logger.add(
            sys.stderr,
            level="INFO",
            enqueue=False,
            backtrace=False,
            diagnose=False,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
        )
        _CONFIGURED = True

    logger.add(
        log_path,
        level="DEBUG",
        enqueue=False,
        backtrace=True,
        diagnose=False,
        encoding="utf-8",
        mode="w",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
    )
    logger.info("logging configured for run={}, log_path={}", run_name, log_path)
    return log_path
