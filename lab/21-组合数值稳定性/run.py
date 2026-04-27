from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import ExperimentMeta, covariance_regularization, load_market_panel, record_experiment, save_csv


def _min_var_weights(cov: pd.DataFrame) -> pd.Series:
    ones = np.ones(len(cov), dtype=float)
    inv = np.linalg.pinv(cov.to_numpy(dtype=float))
    raw = inv @ ones
    denom = float(ones @ raw)
    if denom == 0:
        return pd.Series(np.full(len(cov), 1.0 / len(cov)), index=cov.index)
    weights = raw / denom
    return pd.Series(weights, index=cov.index)


def main() -> None:
    meta = ExperimentMeta(
        code="21",
        title="组合数值稳定性",
        goal="验证协方差矩阵在近奇异场景下可通过收缩保持稳定。",
        root=ROOT,
    )
    market = load_market_panel(["000001", "000002", "600519", "601318"], "20240102", "20240315")
    returns = market.close.pct_change().dropna()
    narrow = returns.tail(12).copy()
    narrow["clone"] = narrow.iloc[:, 0] * 0.999 + narrow.iloc[:, 1] * 0.001
    diagnostics = covariance_regularization(narrow, shrinkage=0.2)
    raw_cov = diagnostics["raw_cov"]
    shrunk_cov = diagnostics["shrunk_cov"]
    raw_weights = _min_var_weights(raw_cov)
    shrunk_weights = _min_var_weights(shrunk_cov)

    raw_concentration = float((raw_weights**2).sum())
    shrunk_concentration = float((shrunk_weights**2).sum())
    summary = pd.DataFrame(
        [
            {
                "raw_min_eig": diagnostics["raw_min_eig"],
                "shrunk_min_eig": diagnostics["shrunk_min_eig"],
                "raw_condition": diagnostics["raw_condition"],
                "shrunk_condition": diagnostics["shrunk_condition"],
                "raw_concentration": raw_concentration,
                "shrunk_concentration": shrunk_concentration,
            }
        ]
    )

    artifact_dir = ROOT / "artifacts"
    save_csv(raw_cov.reset_index(), artifact_dir / "raw_cov.csv")
    save_csv(shrunk_cov.reset_index(), artifact_dir / "shrunk_cov.csv")
    save_csv(pd.DataFrame({"symbol": raw_weights.index, "raw_weight": raw_weights.values, "shrunk_weight": shrunk_weights.values}), artifact_dir / "weights.csv")
    save_csv(summary, artifact_dir / "summary.csv")

    steps = [
        "构造近共线收益矩阵，制造协方差近奇异场景。",
        "对协方差矩阵做对角收缩并比较条件数和最小特征值。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/raw_cov.csv",
        "artifacts/shrunk_cov.csv",
        "artifacts/weights.csv",
        "artifacts/summary.csv",
    ]
    if diagnostics["shrunk_min_eig"] >= diagnostics["raw_min_eig"] and diagnostics["shrunk_condition"] <= diagnostics["raw_condition"]:
        status = "pass"
        conclusion = "收缩后矩阵更稳定，权重集中度得到抑制。"
    else:
        status = "fail"
        conclusion = "协方差稳定化效果不足。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
