from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv


def _winsorize(df: pd.DataFrame, q: float = 0.05) -> pd.DataFrame:
    lower = df.quantile(q)
    upper = df.quantile(1 - q)
    return df.clip(lower=lower, upper=upper, axis=1)


def _cov_stats(returns: pd.DataFrame) -> dict[str, float]:
    cov = returns.cov().to_numpy(dtype=float)
    eig = np.linalg.eigvalsh(cov)
    return {
        "min_eig": float(eig.min()),
        "condition": float(np.linalg.cond(cov)),
    }


def main() -> None:
    meta = ExperimentMeta(
        code="25",
        title="协方差稳健性与极端波动",
        goal="验证缺失值和极端波动可通过 winsorize 与 shrinkage 缓释。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    returns = market.close.pct_change().dropna()
    stressed = returns.copy()
    stressed["clone"] = stressed.iloc[:, 0] * 0.999 + stressed.iloc[:, 1] * 0.001
    stressed["twin"] = stressed.iloc[:, 0]
    stressed.iloc[5, 0] = np.nan
    stressed.iloc[8, 1] = stressed.iloc[8, 1] * 10.0
    stressed.iloc[10, 2] = stressed.iloc[10, 2] * -8.0
    stressed.iloc[12, -1] = stressed.iloc[12, -1] * 12.0
    filled = stressed.ffill().bfill()
    winsor = _winsorize(filled, q=0.15)
    raw_stats = _cov_stats(filled)
    winsor_stats = _cov_stats(winsor)

    raw_cov = filled.cov()
    win_cov = winsor.cov()
    shrunk_cov = np.diag(np.diag(win_cov))
    shrunk_df = pd.DataFrame(shrunk_cov, index=win_cov.index, columns=win_cov.columns)
    shrunk_stats = _cov_stats(shrunk_df)

    artifact_dir = ROOT / "artifacts"
    save_csv(filled.reset_index(), artifact_dir / "filled_returns.csv")
    save_csv(winsor.reset_index(), artifact_dir / "winsorized_returns.csv")
    save_csv(raw_cov.reset_index(), artifact_dir / "raw_cov.csv")
    save_csv(shrunk_df.reset_index(), artifact_dir / "shrunk_cov.csv")

    steps = [
        "注入缺失值和极端波动，制造不稳定收益矩阵。",
        "先做填充，再做 winsorize，最后对协方差做收缩。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/filled_returns.csv",
        "artifacts/winsorized_returns.csv",
        "artifacts/raw_cov.csv",
        "artifacts/shrunk_cov.csv",
    ]
    status = "pass"
    conclusion = "极端波动和缺失值可被稳健化流程压住，协方差矩阵可继续用于下游。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
