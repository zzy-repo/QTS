from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    """保存数据表到 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    logger.info("saved frame path={} rows={} columns={}", path, len(frame), list(frame.columns))


def save_text(text: str, path: Path) -> None:
    """保存文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    logger.info("saved text path={} bytes={}", path, len(text.encode('utf-8')))
