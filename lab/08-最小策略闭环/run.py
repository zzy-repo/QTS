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
        code="08",
        title="最小策略闭环",
        goal="打通「数据 → 信号 → 持仓 → 收益」。",
        root=ROOT,
    )
    start_date = "20240102"
    end_date = "20240315"
    panel = load_close_panel(DEFAULT_UNIVERSE, start_date, end_date)
    mode = panel.attrs.get("source_mode", "unknown")
    run = build_momentum_portfolio(panel, lookback=20, top_n=3, scheme="equal")

    holdings_path = ROOT / "artifacts" / "holdings.csv"
    pnl_path = ROOT / "artifacts" / "pnl.csv"
    save_csv(run.holdings, holdings_path)
    save_csv(run.pnl, pnl_path)

    steps = [
        f"使用固定股票池 {', '.join(DEFAULT_UNIVERSE)}。",
        f"面板来源：{mode}。",
        "按过去 20 日收益排序，选前 3 只等权持仓。",
        f"生成 {len(run.holdings)} 条持仓记录和 {len(run.pnl)} 条日收益记录。",
    ]
    artifacts = ["artifacts/holdings.csv", "artifacts/pnl.csv"]
    if run.pnl.empty:
        status = "fail"
        conclusion = "策略未形成连续收益序列。"
    else:
        status = "pass"
        conclusion = "策略能连续运行并输出收益序列。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
