from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

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
        code="09",
        title="回测引擎闭环",
        goal="建立基础回测能力。",
        root=ROOT,
    )
    panel = load_close_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    mode = panel.attrs.get("source_mode", "unknown")
    run_a = build_momentum_portfolio(panel, lookback=20, top_n=3, scheme="equal")
    run_b = build_momentum_portfolio(panel, lookback=20, top_n=3, scheme="equal")

    pnl_path = ROOT / "artifacts" / "pnl.csv"
    save_csv(run_a.pnl, pnl_path)
    same_output = run_a.pnl.equals(run_b.pnl) and run_a.holdings.equals(run_b.holdings)
    check_path = ROOT / "artifacts" / "reproducibility.txt"
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(
        f"reproducible={same_output}\nrows={len(run_a.pnl)}\n",
        encoding="utf-8",
    )

    steps = [
        "基于历史数据逐日推进，模拟持仓变化。",
        f"面板来源：{mode}。",
        "同一输入运行两次，比较持仓与收益是否一致。",
        f"输出 {len(run_a.pnl)} 条累计收益记录和日收益记录。",
    ]
    artifacts = ["artifacts/pnl.csv", "artifacts/reproducibility.txt"]
    if same_output and not run_a.pnl.empty:
        status = "pass"
        conclusion = "回测结果可复现，固定输入产生固定输出。"
    else:
        status = "fail"
        conclusion = "回测结果未满足复现要求或未形成有效序列。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
