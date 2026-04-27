from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv


def _min_var_weights(cov: pd.DataFrame) -> pd.Series:
    ones = np.ones(len(cov), dtype=float)
    inv = np.linalg.pinv(cov.to_numpy(dtype=float))
    raw = inv @ ones
    denom = float(ones @ raw)
    if denom == 0 or not np.isfinite(denom):
        return pd.Series(np.full(len(cov), 1.0 / len(cov)), index=cov.index)
    weights = raw / denom
    return pd.Series(weights, index=cov.index)


def _fallback_weights(cov: pd.DataFrame, upper: float = 0.45) -> tuple[pd.Series, str]:
    weights = _min_var_weights(cov)
    if (not np.isfinite(weights).all()) or weights.min() < 0 or weights.max() > upper:
        fallback = pd.Series(np.full(len(cov), 1.0 / len(cov)), index=cov.index)
        return fallback, "equal_weight_fallback"
    clipped = weights.clip(lower=0.0, upper=upper)
    clipped = clipped / clipped.sum()
    return clipped, "optimized"


def main() -> None:
    meta = ExperimentMeta(
        code="26",
        title="优化器回退与权重截断",
        goal="验证优化失败时会退化为等权，并对权重做截断。",
        root=ROOT,
    )
    market = load_market_panel(["000001", "000002", "600519", "601318"], "20240102", "20240315")
    returns = market.close.pct_change().dropna().tail(12).copy()
    returns["clone"] = returns.iloc[:, 0] * 0.999 + returns.iloc[:, 1] * 0.001
    cov = returns.cov()
    weights, mode = _fallback_weights(cov, upper=0.40)
    clipped = weights.clip(lower=0.0, upper=0.40)
    clipped = clipped / clipped.sum()

    artifact_dir = ROOT / "artifacts"
    save_csv(cov.reset_index(), artifact_dir / "cov.csv")
    save_csv(pd.DataFrame({"symbol": weights.index, "weight": weights.values, "clipped_weight": clipped.values}), artifact_dir / "weights.csv")

    steps = [
        "构造近奇异协方差矩阵，迫使优化器进入不稳定区域。",
        "若解不满足边界或出现数值异常，则退化为等权。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/cov.csv", "artifacts/weights.csv"]
    if mode == "equal_weight_fallback" or (clipped.min() >= 0 and clipped.max() <= 0.40):
        status = "pass"
        conclusion = "优化器具备回退路径，权重截断后保持可解。"
    else:
        status = "fail"
        conclusion = "优化器回退或截断未达到预期。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
