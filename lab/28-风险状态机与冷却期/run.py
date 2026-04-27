from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, risk_state_machine, save_csv


def main() -> None:
    meta = ExperimentMeta(
        code="28",
        title="风险状态机与冷却期",
        goal="验证 drawdown 和波动率可驱动风险状态切换与冷却期。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    equity = (1.0 + market.close.pct_change().mean(axis=1).fillna(0.0)).cumprod()
    shock_dates = equity.index[20:23]
    equity.loc[shock_dates] = equity.loc[shock_dates] * [0.95, 0.90, 0.88]
    state_df = risk_state_machine(equity, window=10, drawdown_warn=-0.02, drawdown_halt=-0.05, vol_warn=0.10, vol_halt=0.20)

    exposure_map = {"normal": 1.0, "caution": 0.8, "halt": 0.0}
    exposures: list[float] = []
    cooldown = 0
    cooldown_days = 3
    for state in state_df["state"]:
        if cooldown > 0:
            exposures.append(0.0)
            cooldown -= 1
            continue
        exposure = exposure_map.get(state, 1.0)
        exposures.append(exposure)
        if state == "halt":
            cooldown = cooldown_days
    state_df = state_df.copy()
    state_df["exposure"] = exposures
    state_df["cooldown"] = state_df["state"].eq("halt").cumsum()

    artifact_dir = ROOT / "artifacts"
    save_csv(state_df.reset_index().rename(columns={"index": "date"}), artifact_dir / "risk_state.csv")

    has_halt = bool((state_df["state"] == "halt").any())
    cooldown_effective = bool((pd.Series(exposures) == 0.0).sum() > (state_df["state"] == "halt").sum())
    steps = [
        "对权益曲线注入冲击，触发风险状态变化。",
        "把状态映射到仓位暴露，并加入冷却期。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/risk_state.csv"]
    if has_halt and cooldown_effective:
        status = "pass"
        conclusion = "风险状态机可切换，冷却期会延长降仓效果。"
    else:
        status = "fail"
        conclusion = "风险状态机或冷却期未按预期工作。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
