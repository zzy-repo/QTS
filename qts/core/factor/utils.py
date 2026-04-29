from __future__ import annotations

import pandas as pd


def serialize_ts(value: object) -> str:
    """把时间值序列化为字符串。"""
    ts = pd.Timestamp(value)
    if ts.time() == pd.Timestamp(ts.date()).time():
        return ts.strftime("%Y-%m-%d")
    return ts.strftime("%Y-%m-%d %H:%M:%S")
