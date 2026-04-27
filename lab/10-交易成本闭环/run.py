from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    apply_costs,
    build_momentum_portfolio,
    load_close_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="10",
        title="交易成本闭环",
        goal="验证策略在真实摩擦下是否仍成立。",
        root=ROOT,
    )
    panel = load_close_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    mode = panel.attrs.get("source_mode", "unknown")
    run = build_momentum_portfolio(panel, lookback=20, top_n=3, scheme="equal")
    with_cost = apply_costs(run.pnl, fee_bps=5, slippage_bps=1)

    no_cost_path = ROOT / "artifacts" / "no_cost.csv"
    cost_path = ROOT / "artifacts" / "with_cost.csv"
    save_csv(run.pnl, no_cost_path)
    save_csv(with_cost, cost_path)

    steps = [
        "基于同一组合回测结果引入手续费和滑点。",
        f"面板来源：{mode}。",
        "手续费设为万 5，滑点设为 1 bp。",
        "对比有无成本下的收益序列变化。",
    ]
    artifacts = ["artifacts/no_cost.csv", "artifacts/with_cost.csv"]
    if with_cost.empty:
        status = "fail"
        conclusion = "交易成本闭环未输出有效结果。"
    else:
        gross_final = float(run.pnl["equity"].iloc[-1]) if not run.pnl.empty else 1.0
        net_final = float(with_cost["net_equity"].iloc[-1])
        finite = with_cost[["cost", "net_return", "net_equity"]].replace([float("inf"), float("-inf")], float("nan")).notna().all().all()
        if finite and net_final <= gross_final:
            status = "pass"
            conclusion = "引入成本后收益合理收敛，未出现异常爆炸。"
        else:
            status = "fail"
            conclusion = "成本处理后出现异常值或收益方向不合理。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
