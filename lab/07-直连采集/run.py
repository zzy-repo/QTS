from __future__ import annotations

from pathlib import Path
import sys

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import ExperimentMeta, record_experiment, save_csv

TARGET_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
TARGET_PARAMS = {
    "fields1": "f1,f2,f3,f4,f5,f6",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
    "ut": "7eea3edcaed734bea9cbfc24409ed989",
    "klt": "101",
    "fqt": "1",
    "secid": "0.000001",
    "beg": "20240301",
    "end": "20240315",
}


def _fetch() -> pd.DataFrame:
    with httpx.Client(timeout=15, follow_redirects=True, trust_env=False) as client:
        response = client.get(TARGET_URL, params=TARGET_PARAMS)
        response.raise_for_status()
        payload = response.json()
    klines = payload["data"]["klines"]
    df = pd.DataFrame([row.split(",") for row in klines])
    df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "amplitude",
        "pct_change",
        "change",
        "turnover",
    ]
    df["symbol"] = "000001"
    df = df[
        [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "amplitude",
            "pct_change",
            "change",
            "turnover",
        ]
    ]
    return df


def main() -> None:
    meta = ExperimentMeta(
        code="07",
        title="直连采集",
        goal="验证同一东财接口在 httpx 直连下是否可以稳定采集历史行情。",
        root=ROOT,
    )
    data_path = ROOT / "artifacts" / "history.csv"
    steps = [
        "使用与 AkShare 相同的东财 kline 接口。",
        "改用 httpx.Client(trust_env=False) 直接请求并解析 JSON。",
        "将返回的 kline 切分并整理为标准字段。",
    ]
    artifacts = ["artifacts/history.csv"]
    try:
        df = _fetch()
        save_csv(df, data_path)
        steps.append(f"成功采集 {len(df)} 行历史行情。")
        status = "pass"
        conclusion = "同一接口在 httpx 直连下可用，说明可继续沿这条链路做数据获取。"
    except Exception as exc:
        steps.append(f"直连采集失败：{exc!r}")
        status = "fail"
        conclusion = "同一接口在 httpx 直连下仍不可用，需要继续拆分请求头或响应差异。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
