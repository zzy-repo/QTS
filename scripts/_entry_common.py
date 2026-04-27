from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    """保存数据表到 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def save_text(text: str, path: Path) -> None:
    """保存文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
