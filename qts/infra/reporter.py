from __future__ import annotations

import pandas as pd

from ..core.analysis import performance_summary_from_pnl
from ..core.portfolio.results import SystemRunResult, daily_pnl_view, final_annualized_return

def summarize_system_run(result: SystemRunResult, benchmark: pd.Series | None = None) -> pd.DataFrame:
    """汇总系统运行结果。"""
    rows: list[dict[str, object]] = []
    final_equity = float(result.aggregate_equity["equity"].iloc[-1]) if not result.aggregate_equity.empty else 0.0
    aggregate_daily = daily_pnl_view(result.aggregate_pnl)
    aggregate_annualized_return = final_annualized_return(aggregate_daily)
    for run in result.strategy_runs:
        pnl = run.execution.pnl
        metric_row = performance_summary_from_pnl(pnl, benchmark=benchmark, turnover_column="turnover").iloc[0].to_dict()
        rows.append(
            {
                "strategy": run.name,
                "allocation_cash": run.allocation_cash,
                "signal_rows": len(run.signals),
                "pnl_rows": len(pnl),
                "final_equity": float(pnl["equity"].iloc[-1]) if not pnl.empty else 0.0,
                "annualized_return": final_annualized_return(pnl),
                **metric_row,
            }
        )
    aggregate_metrics = performance_summary_from_pnl(aggregate_daily, benchmark=benchmark).iloc[0].to_dict()
    rows.append(
        {
            "strategy": "aggregate",
            "allocation_cash": result.allocation.allocation["allocated_cash"].sum() if not result.allocation.allocation.empty else 0.0,
            "cash_left": result.allocation.cash_left,
            "signal_rows": len(result.strategy_signals),
            "pnl_rows": len(aggregate_daily),
            "final_equity": final_equity,
            "annualized_return": aggregate_annualized_return,
            **aggregate_metrics,
        }
    )
    return pd.DataFrame(rows)
