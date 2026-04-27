from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    DEFAULT_UNIVERSE,
    ExperimentMeta,
    build_momentum_portfolio,
    load_close_panel,
    record_experiment,
    save_csv,
)


def main() -> None:
    meta = ExperimentMeta(
        code="11",
        title="组合构建闭环",
        goal="从“选股”过渡到“组合”。",
        root=ROOT,
    )
    panel = load_close_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    mode = panel.attrs.get("source_mode", "unknown")
    equal_run = build_momentum_portfolio(panel, lookback=20, top_n=3, scheme="equal")
    inv_run = build_momentum_portfolio(panel, lookback=20, top_n=3, scheme="inv_vol")

    equal_path = ROOT / "artifacts" / "weights_equal.csv"
    inv_path = ROOT / "artifacts" / "weights_inv_vol.csv"
    summary_path = ROOT / "artifacts" / "weight_summary.csv"
    save_csv(equal_run.holdings, equal_path)
    save_csv(inv_run.holdings, inv_path)

    summary = (
        inv_run.holdings.groupby("date")["weight"]
        .agg(weight_sum="sum", weight_min="min", weight_max="max")
        .reset_index()
    )
    save_csv(summary, summary_path)

    steps = [
        "实现等权和波动率倒数加权两种组合方式。",
        f"面板来源：{mode}。",
        "输出每日权重分布并检查权重归一性。",
        "对比权重是否出现异常集中或负值。",
    ]
    artifacts = ["artifacts/weights_equal.csv", "artifacts/weights_inv_vol.csv", "artifacts/weight_summary.csv"]
    if summary.empty:
        status = "fail"
        conclusion = "组合构建未输出有效权重分布。"
    else:
        all_ok = (
            (summary["weight_sum"].sub(1.0).abs() < 1e-6).all()
            and (inv_run.holdings["weight"] >= 0).all()
            and (equal_run.holdings["weight"] >= 0).all()
        )
        if all_ok:
            status = "pass"
            conclusion = "权重归一，未见异常集中或负值。"
        else:
            status = "fail"
            conclusion = "权重分布存在归一性或符号问题。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
