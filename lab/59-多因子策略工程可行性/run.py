from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
REPO_ROOT = LAB_ROOT.parent
sys.path.insert(0, str(LAB_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv

from qts.core.data.models import StrategyInput
from qts.core.factor import get_factor_adapter
from qts.core.strategy import build_strategy_spec
from qts.core.strategy.engine import SignalGenerator
from qts.core.strategy.specs import StrategySpec
from qts.core.strategy.validators import validate_strategy_output
from qts.infra.system import MultiDecisionSystem


@dataclass(frozen=True)
class MultiFactorPrototype:
    name: str
    factor_kinds: tuple[str, ...]
    factor_weights: dict[str, float]
    lookback: int = 20
    top_n: int = 3

    def build_spec(self) -> StrategySpec:
        return StrategySpec(
            name=self.name,
            builder=build_multi_factor_builder(
                factor_kinds=self.factor_kinds,
                factor_weights=self.factor_weights,
                lookback=self.lookback,
                top_n=self.top_n,
            ),
            strategy_kind="factor",
            factor_kinds=list(self.factor_kinds),
            factor_weights=dict(self.factor_weights),
            lookback=self.lookback,
            top_n=self.top_n,
        )


def _strategy_input(data: StrategyInput, *, lookback: int, top_n: int) -> StrategyInput:
    return StrategyInput(
        close=data.close,
        volume=data.volume,
        amount=data.amount,
        lookback=lookback,
        top_n=top_n,
    )


def _zscore(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    std = float(values.std(ddof=0))
    if not np.isfinite(std) or std <= 0.0:
        return pd.Series(0.0, index=series.index, dtype=float)
    mean = float(values.mean())
    return (values - mean) / std


def _normalize_factor_signal(signal: pd.DataFrame, factor_kind: str) -> pd.DataFrame:
    frame = signal[["date", "symbol", "score"]].copy()
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    frame = frame.dropna(subset=["score"])
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol"])
    frame[f"score_{factor_kind}"] = frame.groupby("date", group_keys=False)["score"].transform(_zscore)
    frame[f"selected_{factor_kind}"] = 1.0
    return frame.drop(columns=["score"])


def _blend_weights(selected: pd.DataFrame) -> pd.Series:
    shifted = selected["score"] - float(selected["score"].min())
    positive = shifted.clip(lower=0.0)
    total = float(positive.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(selected), index=selected.index, dtype=float)
    return positive / total


def build_multi_factor_builder(
    *,
    factor_kinds: tuple[str, ...],
    factor_weights: dict[str, float],
    lookback: int,
    top_n: int,
):
    normalized_weights = pd.Series(factor_weights, dtype=float).reindex(list(factor_kinds)).fillna(0.0)
    if float(normalized_weights.abs().sum()) <= 0.0:
        normalized_weights.loc[:] = 1.0
    normalized_weights = normalized_weights / float(normalized_weights.abs().sum())

    def builder(data: StrategyInput) -> pd.DataFrame:
        merged: pd.DataFrame | None = None
        strategy_data = _strategy_input(data, lookback=lookback, top_n=top_n)
        for factor_kind in factor_kinds:
            factor_signal = get_factor_adapter(factor_kind).run(strategy_data).copy()
            normalized = _normalize_factor_signal(factor_signal, factor_kind)
            if normalized.empty:
                continue
            if merged is None:
                merged = normalized
            else:
                merged = merged.merge(normalized, on=["date", "symbol"], how="outer")
        if merged is None or merged.empty:
            return pd.DataFrame(columns=["date", "symbol", "rank", "score", "weight", "factor_hits"])

        score_columns = [f"score_{factor_kind}" for factor_kind in factor_kinds if f"score_{factor_kind}" in merged.columns]
        hit_columns = [f"selected_{factor_kind}" for factor_kind in factor_kinds if f"selected_{factor_kind}" in merged.columns]
        merged[score_columns] = merged[score_columns].fillna(0.0)
        merged[hit_columns] = merged[hit_columns].fillna(0.0)
        merged["factor_hits"] = merged[hit_columns].sum(axis=1)
        merged["score"] = 0.0
        for factor_kind in factor_kinds:
            score_column = f"score_{factor_kind}"
            if score_column not in merged.columns:
                continue
            merged["score"] = merged["score"] + merged[score_column] * float(normalized_weights[factor_kind])

        rows: list[dict[str, object]] = []
        for date, group in merged.groupby("date", sort=True):
            selected = group.sort_values(["score", "factor_hits", "symbol"], ascending=[False, False, True]).head(top_n).copy()
            if selected.empty:
                continue
            weights = _blend_weights(selected)
            for rank, (_, row) in enumerate(selected.iterrows(), start=1):
                rows.append(
                    {
                        "date": date,
                        "symbol": row["symbol"],
                        "rank": rank,
                        "score": float(row["score"]),
                        "weight": float(weights.loc[row.name]),
                        "factor_hits": int(row["factor_hits"]),
                    }
                )
        return pd.DataFrame(rows)

    return builder


def _build_input(market, *, lookback: int, top_n: int) -> StrategyInput:
    return StrategyInput(
        close=market.close,
        volume=market.volume,
        amount=market.amount,
        lookback=lookback,
        top_n=top_n,
    )


def _coverage_summary(raw_signals: dict[str, pd.DataFrame], market_symbols: int) -> pd.DataFrame:
    union_frame: pd.DataFrame | None = None
    for factor_kind, signal in raw_signals.items():
        frame = signal[["date", "symbol"]].copy()
        frame[f"selected_{factor_kind}"] = 1
        if union_frame is None:
            union_frame = frame
        else:
            union_frame = union_frame.merge(frame, on=["date", "symbol"], how="outer")
    if union_frame is None or union_frame.empty:
        return pd.DataFrame()
    selected_columns = [column for column in union_frame.columns if column.startswith("selected_")]
    union_frame[selected_columns] = union_frame[selected_columns].fillna(0)
    union_frame["factor_hits"] = union_frame[selected_columns].sum(axis=1)
    daily = union_frame.groupby("date", as_index=False).agg(
        union_candidates=("symbol", "nunique"),
        overlap_candidates=("factor_hits", lambda values: int((pd.Series(values) >= 2).sum())),
        avg_factor_hits=("factor_hits", "mean"),
    )
    daily["universe_symbols"] = market_symbols
    daily["coverage_ratio"] = daily["union_candidates"] / float(market_symbols) if market_symbols else np.nan
    return daily


def _strategy_run_summary(result) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for run in result.strategy_runs:
        rows.append(
            {
                "strategy": run.name,
                "signal_rows": len(run.signals),
                "optimized_rows": len(run.optimized),
                "order_rows": len(run.execution.orders),
                "pnl_rows": len(run.execution.pnl),
                "allocation_cash": float(run.allocation_cash),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="59",
        title="多因子策略工程可行性",
        goal="验证在不修改主干代码的前提下，能否以实验方式把多个单因子组合成一个可执行策略。",
        root=ROOT,
    )

    lookback = 20
    top_n = 3
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    data = _build_input(market, lookback=lookback, top_n=top_n)

    factor_kinds = ("momentum", "trend", "sharpe")
    factor_weights = {"momentum": 0.4, "trend": 0.3, "sharpe": 0.3}
    raw_signals = {factor_kind: get_factor_adapter(factor_kind).run(data).copy() for factor_kind in factor_kinds}

    prototype = MultiFactorPrototype(
        name="multi_blend",
        factor_kinds=factor_kinds,
        factor_weights=factor_weights,
        lookback=lookback,
        top_n=top_n,
    )
    multi_spec = prototype.build_spec()
    multi_signal = multi_spec.builder(data).copy()
    multi_issues = validate_strategy_output(multi_signal)

    single_spec = build_strategy_spec(
        "single_momentum",
        strategy_kind="factor",
        factor_kinds=["momentum"],
        lookback=lookback,
        top_n=top_n,
    )
    signal_generator = SignalGenerator(strategies=[single_spec, multi_spec])
    generated = signal_generator.generate(market)

    system = MultiDecisionSystem(
        strategies=[single_spec, multi_spec],
        allocation_mode="score",
        optimizer_mode="score",
        execution_mode="backtest",
        initial_cash=1_000_000.0,
        lot_size=100,
    )
    result = system.run(market)

    coverage = _coverage_summary(raw_signals, market_symbols=len(market.close.columns))
    strategy_summary = _strategy_run_summary(result)
    feasibility = pd.DataFrame(
        [
            {
                "validation_ok": not multi_issues,
                "pipeline_ok": not result.aggregate_pnl.empty,
                "generated_rows": len(generated),
                "multi_signal_rows": len(multi_signal),
                "mean_union_candidates": float(coverage["union_candidates"].mean()) if not coverage.empty else np.nan,
                "mean_coverage_ratio": float(coverage["coverage_ratio"].mean()) if not coverage.empty else np.nan,
                "mean_overlap_candidates": float(coverage["overlap_candidates"].mean()) if not coverage.empty else np.nan,
                "mean_factor_hits": float(coverage["avg_factor_hits"].mean()) if not coverage.empty else np.nan,
                "market_symbols": len(market.close.columns),
                "raw_factor_top_n": top_n,
            }
        ]
    )

    artifact_dir = ROOT / "artifacts"
    save_csv(multi_signal, artifact_dir / "multi_factor_signal.csv")
    save_csv(generated, artifact_dir / "generated_signals.csv")
    save_csv(coverage, artifact_dir / "coverage_summary.csv")
    save_csv(strategy_summary, artifact_dir / "strategy_run_summary.csv")
    save_csv(result.aggregate_pnl, artifact_dir / "aggregate_pnl.csv")
    save_csv(feasibility, artifact_dir / "feasibility_summary.csv")

    validation_ok = not multi_issues
    pipeline_ok = not result.aggregate_pnl.empty
    coexist_ok = bool((strategy_summary["signal_rows"] > 0).all()) if not strategy_summary.empty else False
    coverage_limited = bool((coverage["coverage_ratio"] < 1.0).any()) if not coverage.empty else True
    overlap_exists = bool((coverage["overlap_candidates"] > 0).any()) if not coverage.empty else False

    steps = [
        "在实验目录内实现一个多因子 builder，把多个单因子信号合成为统一策略输出。",
        "直接复用现有 StrategySpec、SignalGenerator 和 MultiDecisionSystem，验证下游流水线无需改动即可运行。",
        f"组合因子：{', '.join(factor_kinds)}；权重：{factor_weights}；行情来源：{market.source_mode}。",
        "额外统计候选覆盖率，检查当前因子接口是否只暴露 top_n 结果，从而限制多因子在策略层做完整横截面融合。",
    ]
    artifacts = [
        "artifacts/multi_factor_signal.csv",
        "artifacts/generated_signals.csv",
        "artifacts/coverage_summary.csv",
        "artifacts/strategy_run_summary.csv",
        "artifacts/aggregate_pnl.csv",
        "artifacts/feasibility_summary.csv",
    ]
    if validation_ok and pipeline_ok and coexist_ok and overlap_exists:
        status = "pass"
        if coverage_limited:
            conclusion = "多因子策略在工程上可通过自定义 builder 接入现有流水线，但当前因子层只输出入选 top_n，限制了策略层做完整横截面融合。"
        else:
            conclusion = "多因子策略在工程上可通过自定义 builder 接入现有流水线，且当前样本下未暴露明显接口瓶颈。"
    else:
        status = "fail"
        conclusion = "多因子策略原型未能稳定接入现有流水线，仍需补足策略输出或下游兼容性。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
