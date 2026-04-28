from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    apply_costs,
    build_momentum_portfolio,
    load_market_panel,
    record_experiment,
    risk_state_machine,
    save_csv,
)
from shared.feasibility import compute_tail_metrics


def _returns_from_market(market) -> pd.Series:
    run = build_momentum_portfolio(market.close, lookback=20, top_n=3, scheme="equal")
    costed = apply_costs(run.pnl, fee_bps=5, slippage_bps=1)
    series = pd.Series(costed["net_return"].values, index=pd.to_datetime(costed["date"]))
    return series


def _stress_scenarios(base: pd.Series) -> dict[str, pd.Series]:
    scenarios: dict[str, pd.Series] = {"base": base.copy()}
    idx = base.index
    high_vol = base.copy()
    high_vol = high_vol * (1.0 + 0.8 * np.sin(np.linspace(0, 8, len(high_vol))))
    scenarios["high_volatility"] = high_vol

    drawdown = base.copy()
    if len(drawdown) >= 20:
        window = drawdown.index[10:18]
        drawdown.loc[window] = drawdown.loc[window] - np.linspace(0.01, 0.04, len(window))
    scenarios["drawdown_cluster"] = drawdown

    crash = base.copy()
    if len(crash) >= 12:
        crash_window = crash.index[8:14]
        crash.loc[crash_window] = -np.abs(crash.loc[crash_window].values) - np.linspace(0.015, 0.05, len(crash_window))
    scenarios["continuous_down"] = crash
    return scenarios


def _apply_cooldown(returns: pd.Series, state_df: pd.DataFrame, cooldown_days: int) -> pd.DataFrame:
    exposure_map = {"normal": 1.0, "caution": 0.7, "halt": 0.0}
    exposures: list[float] = []
    cooldown = 0
    for state in state_df["state"].tolist():
        if cooldown > 0:
            exposures.append(0.0)
            cooldown -= 1
            continue
        exposure = exposure_map.get(state, 1.0)
        exposures.append(exposure)
        if state == "halt":
            cooldown = cooldown_days
    out = state_df.copy()
    out["exposure"] = exposures
    out["adjusted_return"] = returns.values[: len(out)] * out["exposure"].values
    out["adjusted_equity"] = (1.0 + out["adjusted_return"]).cumprod()
    return out


def main() -> None:
    meta = ExperimentMeta(
        code="50",
        title="风险管理敏感性",
        goal="测试不同回撤阈值、冷却期和极端市场情景下的风险控制效果。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20220103", "20240315")
    base_returns = _returns_from_market(market)
    scenarios = _stress_scenarios(base_returns)
    configs = [
        {"label": "tight", "drawdown_warn": -0.02, "drawdown_halt": -0.05, "vol_warn": 0.10, "vol_halt": 0.18, "cooldown_days": 5},
        {"label": "base", "drawdown_warn": -0.03, "drawdown_halt": -0.08, "vol_warn": 0.15, "vol_halt": 0.25, "cooldown_days": 3},
        {"label": "loose", "drawdown_warn": -0.05, "drawdown_halt": -0.12, "vol_warn": 0.20, "vol_halt": 0.30, "cooldown_days": 0},
    ]

    rows: list[dict[str, object]] = []
    for scenario_name, returns in scenarios.items():
        equity = (1.0 + returns.fillna(0.0)).cumprod()
        for config in configs:
            state_df = risk_state_machine(
                equity,
                window=20,
                drawdown_warn=config["drawdown_warn"],
                drawdown_halt=config["drawdown_halt"],
                vol_warn=config["vol_warn"],
                vol_halt=config["vol_halt"],
            )
            adjusted = _apply_cooldown(returns.reindex(state_df.index).fillna(0.0), state_df, config["cooldown_days"])
            tail = compute_tail_metrics(adjusted["adjusted_return"])
            rows.append(
                {
                    "scenario": scenario_name,
                    "config": config["label"],
                    "drawdown_warn": config["drawdown_warn"],
                    "drawdown_halt": config["drawdown_halt"],
                    "cooldown_days": config["cooldown_days"],
                    "halt_days": int((state_df["state"] == "halt").sum()),
                    "caution_days": int((state_df["state"] == "caution").sum()),
                    "final_equity": float(adjusted["adjusted_equity"].iloc[-1]) if not adjusted.empty else np.nan,
                    "mdd": tail["mdd"],
                    "sortino": tail["sortino"],
                    "cvar": tail["cvar"],
                    "win_rate": tail["win_rate"],
                    "avg_exposure": float(adjusted["exposure"].mean()) if not adjusted.empty else np.nan,
                }
            )

    summary = pd.DataFrame(rows)
    artifact_dir = ROOT / "artifacts"
    save_csv(summary, artifact_dir / "risk_sensitivity.csv")

    stress_triggered = bool((summary.loc[summary["scenario"] != "base", "halt_days"] > 0).any())
    tighter_more_halt = False
    if not summary.empty:
        base_rows = summary[summary["scenario"] == "base"].set_index("config")
        if {"tight", "loose"}.issubset(base_rows.index):
            tighter_more_halt = bool(base_rows.loc["tight", "halt_days"] >= base_rows.loc["loose", "halt_days"])
    steps = [
        "在基准收益上构造高波动、连续下跌和回撤簇三种极端情景。",
        "用不同回撤阈值、波动阈值和冷却天数驱动风险状态机。",
        "计算 CVaR、Sortino、最大回撤和暴露率。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = ["artifacts/risk_sensitivity.csv"]
    if stress_triggered and tighter_more_halt:
        status = "pass"
        conclusion = "极端情景能触发风控，且更紧的阈值会更早进入防御状态。"
    else:
        status = "fail"
        conclusion = "风险管理敏感性结果未体现出明确的分层效果。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
