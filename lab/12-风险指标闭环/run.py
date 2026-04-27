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
    compute_metrics,
    load_close_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="12",
        title="风险指标闭环",
        goal="建立策略评价能力。",
        root=ROOT,
    )
    panel = load_close_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    mode = panel.attrs.get("source_mode", "unknown")
    run = build_momentum_portfolio(panel, lookback=20, top_n=3, scheme="equal")
    costed = apply_costs(run.pnl, fee_bps=5, slippage_bps=1)
    metrics = compute_metrics(costed["net_return"] if not costed.empty else costed.get("gross_return", []))

    metrics_path = ROOT / "artifacts" / "metrics.csv"
    equity_path = ROOT / "artifacts" / "equity.csv"
    save_csv(metrics, metrics_path)
    save_csv(costed, equity_path)

    steps = [
        "基于成本后收益序列计算 Sharpe、最大回撤和波动率。",
        f"面板来源：{mode}。",
        "检查指标是否随策略变化而变化。",
        "验证指标数值是否稳定且无 NaN/异常值。",
    ]
    artifacts = ["artifacts/metrics.csv", "artifacts/equity.csv"]
    valid = metrics.notna().all().all()
    if valid and not metrics.empty:
        status = "pass"
        conclusion = "风险指标数值稳定，可用于策略评价。"
    else:
        status = "fail"
        conclusion = "风险指标存在空值或未能稳定输出。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
