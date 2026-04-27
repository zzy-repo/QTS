from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .results import SystemRunResult, annualized_return


@dataclass(frozen=True)
class Reporter:
    def summarize(self, result: SystemRunResult) -> pd.DataFrame:
        return summarize_system_run(result)


def summarize_system_run(result: SystemRunResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    final_equity = float(result.aggregate_equity["equity"].iloc[-1]) if not result.aggregate_equity.empty else 0.0
    aggregate_total_return = float(result.aggregate_pnl["cum_return"].iloc[-1]) if not result.aggregate_pnl.empty else 0.0
    aggregate_annualized_return = annualized_return(aggregate_total_return, len(result.aggregate_pnl))
    for run in result.strategy_runs:
        pnl = run.execution.pnl
        total_return = float(pnl["cum_return"].iloc[-1]) if not pnl.empty and "cum_return" in pnl.columns else 0.0
        rows.append(
            {
                "strategy": run.name,
                "allocation_cash": run.allocation_cash,
                "signal_rows": len(run.signals),
                "pnl_rows": len(pnl),
                "final_equity": float(pnl["equity"].iloc[-1]) if not pnl.empty else 0.0,
                "annualized_return": annualized_return(total_return, len(pnl)),
            }
        )
    rows.append(
        {
            "strategy": "aggregate",
            "allocation_cash": result.allocation.allocation["allocated_cash"].sum() if not result.allocation.allocation.empty else 0.0,
            "signal_rows": len(result.strategy_signals),
            "pnl_rows": len(result.aggregate_pnl),
            "final_equity": final_equity,
            "annualized_return": aggregate_annualized_return,
        }
    )
    return pd.DataFrame(rows)

