from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, build_ohlcv_frame, load_market_panel, quality_checks, record_experiment, save_csv


def _inject_missing(frame: pd.DataFrame) -> pd.DataFrame:
    polluted = frame.copy()
    if len(polluted) >= 8:
        polluted.loc[polluted.index[2], "close"] = np.nan
        polluted.loc[polluted.index[4], "volume"] = np.nan
        polluted.loc[polluted.index[6], "amount"] = np.nan
    return polluted


def _fill_ffill(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values("date").copy()
    numeric = [column for column in ["open", "high", "low", "close", "volume", "amount"] if column in out.columns]
    out[numeric] = out[numeric].ffill().bfill()
    return out


def _fill_median(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values("date").copy()
    for column in ["open", "high", "low", "close", "volume", "amount"]:
        if column in out.columns:
            out[column] = out[column].fillna(out[column].median())
    return out


def _check_per_symbol(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for symbol, group in frame.groupby("symbol"):
        issues = quality_checks(group.reset_index(drop=True))
        rows.append(
            {
                "symbol": symbol,
                "rows": len(group),
                "issue_count": len(issues),
                "issues": " | ".join(issues),
                "passed": not issues,
            }
        )
    return rows


def _completeness(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    start = pd.to_datetime(frame["date"]).min()
    end = pd.to_datetime(frame["date"]).max()
    expected = pd.date_range(start, end, freq="B")
    expected_count = len(expected)
    for symbol, group in frame.groupby("symbol"):
        dates = pd.to_datetime(group["date"]).drop_duplicates().sort_values()
        missing = len(expected.difference(dates))
        rows.append(
            {
                "symbol": symbol,
                "expected_days": expected_count,
                "actual_days": len(dates),
                "missing_days": missing,
                "completeness": len(dates) / expected_count if expected_count else np.nan,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="47",
        title="数据质量与历史完整性",
        goal="检验缺失值处理方式与历史数据覆盖率是否满足下游实验需要。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20220103", "20240315")
    ohlcv = build_ohlcv_frame(market)

    polluted_rows: list[pd.DataFrame] = []
    sensitivity_rows: list[dict[str, object]] = []
    for symbol, group in ohlcv.groupby("symbol"):
        group = group.sort_values("date").reset_index(drop=True)
        polluted = _inject_missing(group)
        polluted_rows.append(polluted.assign(method="polluted"))
        methods = {
            "dropna": polluted.dropna().reset_index(drop=True),
            "ffill_bfill": _fill_ffill(polluted),
            "median_fill": _fill_median(polluted),
        }
        for method, frame in methods.items():
            checks = quality_checks(frame.reset_index(drop=True))
            sensitivity_rows.append(
                {
                    "symbol": symbol,
                    "method": method,
                    "rows": len(frame),
                    "issue_count": len(checks),
                    "passed": not checks,
                    "issues": " | ".join(checks),
                }
            )

    polluted_frame = pd.concat(polluted_rows, ignore_index=True) if polluted_rows else pd.DataFrame()
    sensitivity = pd.DataFrame(sensitivity_rows)
    completeness = _completeness(ohlcv)

    artifact_dir = ROOT / "artifacts"
    save_csv(polluted_frame, artifact_dir / "polluted_sample.csv")
    save_csv(sensitivity, artifact_dir / "quality_sensitivity.csv")
    save_csv(completeness, artifact_dir / "historical_completeness.csv")

    completeness_ok = bool((completeness["completeness"] >= 0.95).all()) if not completeness.empty else False
    resolved = bool((sensitivity["method"].isin(["ffill_bfill", "median_fill"]) & sensitivity["passed"]).any())
    steps = [
        "将每个标的的 OHLCV 数据单独做缺失值注入，构造污染样本。",
        "对比 dropna、前向/后向填充和中位数填充三种恢复方式。",
        "按业务日历统计历史覆盖率，检查是否存在明显缺口。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/polluted_sample.csv",
        "artifacts/quality_sensitivity.csv",
        "artifacts/historical_completeness.csv",
    ]
    if completeness_ok and resolved:
        status = "pass"
        conclusion = "缺失值可通过填充恢复，历史覆盖率也满足连续性要求。"
    else:
        status = "fail"
        conclusion = "数据质量或历史完整性存在明显缺口。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
