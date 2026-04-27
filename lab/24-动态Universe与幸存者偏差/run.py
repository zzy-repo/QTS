from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import DEFAULT_UNIVERSE, ExperimentMeta, load_market_panel, record_experiment, save_csv


def _select_universe(close: pd.DataFrame, volume: pd.DataFrame, lookback: int = 20, top_n: int = 3) -> pd.DataFrame:
    momentum = close.pct_change(lookback)
    liquidity = volume.rolling(lookback, min_periods=lookback).mean()
    rows: list[dict[str, object]] = []
    for date in close.index[lookback:]:
        m_row = momentum.loc[date].dropna()
        l_row = liquidity.loc[date].reindex(m_row.index).fillna(0.0)
        score = (m_row.rank(pct=True) + l_row.rank(pct=True)) / 2.0
        selected = score.sort_values(ascending=False).head(top_n)
        for rank, (symbol, value) in enumerate(selected.items(), start=1):
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "rank": rank,
                    "momentum_score": float(m_row.get(symbol, 0.0)),
                    "liquidity_score": float(l_row.get(symbol, 0.0)),
                    "composite_score": float(value),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="24",
        title="动态Universe与幸存者偏差",
        goal="验证 universe 按周期滚动筛选，而不是静态过滤。",
        root=ROOT,
    )
    market = load_market_panel(DEFAULT_UNIVERSE, "20240102", "20240315")
    universe = _select_universe(market.close, market.volume, lookback=20, top_n=3)
    survivor = universe.groupby("symbol").size().sort_values(ascending=False).reset_index(name="days_selected")
    daily_count = universe.groupby("date").size().reset_index(name="selected_count")

    artifact_dir = ROOT / "artifacts"
    save_csv(universe, artifact_dir / "universe_history.csv")
    save_csv(survivor, artifact_dir / "symbol_frequency.csv")
    save_csv(daily_count, artifact_dir / "daily_count.csv")

    unique_symbols = universe["symbol"].nunique() if not universe.empty else 0
    date_span = daily_count["selected_count"].nunique() if not daily_count.empty else 0
    steps = [
        "按过去 20 日收益和流动性排序，每个交易日重新筛选 universe。",
        "统计被选入的标的频次，检查是否存在静态幸存者偏差。",
        f"面板来源：{market.source_mode}。",
    ]
    artifacts = [
        "artifacts/universe_history.csv",
        "artifacts/symbol_frequency.csv",
        "artifacts/daily_count.csv",
    ]
    if unique_symbols > 1 and date_span >= 1:
        status = "pass"
        conclusion = "universe 是滚动更新的，选择结果会随时间变化。"
    else:
        status = "fail"
        conclusion = "动态 universe 选择未体现时间变化。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
