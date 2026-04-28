from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..core.analysis import performance_summary_from_pnl
from ..core.portfolio.results import SystemRunResult, final_annualized_return


@dataclass(frozen=True)
class Reporter:
    """把系统结果汇总成报表。"""

    def summarize(self, result: SystemRunResult, benchmark: pd.Series | None = None) -> pd.DataFrame:
        """生成系统汇总表。"""
        return summarize_system_run(result, benchmark=benchmark)


def summarize_system_run(result: SystemRunResult, benchmark: pd.Series | None = None) -> pd.DataFrame:
    """汇总系统运行结果。"""
    rows: list[dict[str, object]] = []
    final_equity = float(result.aggregate_equity["equity"].iloc[-1]) if not result.aggregate_equity.empty else 0.0
    aggregate_annualized_return = final_annualized_return(result.aggregate_pnl)
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
    aggregate_metrics = performance_summary_from_pnl(result.aggregate_pnl, benchmark=benchmark, turnover_column="allocation_weight").iloc[0].to_dict()
    rows.append(
        {
            "strategy": "aggregate",
            "allocation_cash": result.allocation.allocation["allocated_cash"].sum() if not result.allocation.allocation.empty else 0.0,
            "signal_rows": len(result.strategy_signals),
            "pnl_rows": len(result.aggregate_pnl),
            "final_equity": final_equity,
            "annualized_return": aggregate_annualized_return,
            **aggregate_metrics,
        }
    )
    return pd.DataFrame(rows)
