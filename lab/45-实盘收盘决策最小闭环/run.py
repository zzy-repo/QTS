from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
sys.path.insert(0, str(LAB_ROOT))

from shared import (
    AccountState,
    ExperimentMeta,
    build_momentum_portfolio,
    dynamic_slippage_cost,
    execute_rebalance,
    normalize_daily_history,
    quality_checks,
    record_experiment,
    risk_state_machine,
    save_csv,
)


SYMBOLS = ["000001", "600519", "601318"]


def _make_raw_history(symbol: str, start_date: str, end_date: str, phase: float) -> pd.DataFrame:
    dates = pd.bdate_range(pd.to_datetime(start_date), pd.to_datetime(end_date))
    idx = np.arange(len(dates), dtype=float)
    base = 100.0 + 2.5 * phase
    close = base + 0.7 * idx + np.sin(idx / 3.0 + phase) * (1.0 + 0.2 * phase)
    open_ = close * (1.0 - 0.0015 + 0.0002 * phase)
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = 1_000_000.0 + idx * (4_000.0 + 500.0 * phase)
    amount = close * volume
    pct_change = pd.Series(close).pct_change().fillna(0.0) * 100.0
    change = pd.Series(close - open_).fillna(0.0)
    turnover = 0.5 + 0.01 * phase + idx * 0.002
    return pd.DataFrame(
        {
            "日期": dates.strftime("%Y-%m-%d"),
            "开盘": open_,
            "收盘": close,
            "最高": high,
            "最低": low,
            "成交量": volume,
            "成交额": amount,
            "振幅": (high / low - 1.0) * 100.0,
            "涨跌幅": pct_change.to_numpy(),
            "涨跌额": change.to_numpy(),
            "换手率": turnover,
        }
    )


def _build_market_panel(frames: list[pd.DataFrame]) -> object:
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    close = combined.pivot(index="date", columns="symbol", values="close").sort_index()
    volume = combined.pivot(index="date", columns="symbol", values="volume").sort_index()
    amount = combined.pivot(index="date", columns="symbol", values="amount").sort_index()
    from shared import MarketPanel

    return MarketPanel(close=close, volume=volume, amount=amount, source_mode="lab-synthetic-close")


def _build_advice(
    target_row: pd.Series,
    current_positions: dict[str, float],
    price_row: pd.Series,
    amount_row: pd.Series,
    volatility_row: pd.Series,
    risk_state: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in price_row.index:
        current = float(current_positions.get(symbol, 0.0))
        target = float(target_row.get(symbol, 0.0))
        delta = target - current
        if abs(delta) < 1e-9:
            action = "持有"
        elif target == 0.0 and current > 0.0:
            action = "清仓"
        elif delta > 0:
            action = "买入"
        else:
            action = "卖出"
        notional = abs(delta) * float(price_row.get(symbol, 0.0))
        slippage = dynamic_slippage_cost(
            notional,
            float(amount_row.get(symbol, 0.0)),
            float(volatility_row.get(symbol, 0.0)),
        )
        rows.append(
            {
                "symbol": symbol,
                "risk_state": risk_state,
                "current_shares": current,
                "target_shares": target,
                "delta_shares": delta,
                "action": action,
                "trade_notional": notional,
                "estimated_slippage": slippage,
            }
        )
    return pd.DataFrame(rows)


def _simulate_schedule(
    market,
    *,
    lookback: int,
    top_n: int,
    window_count: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    dates = list(market.close.index)
    start = max(lookback + 2, 1)
    stop = min(len(dates), start + window_count)
    for idx in range(start, stop):
        sub_market = type(market)(
            close=market.close.iloc[: idx + 1],
            volume=market.volume.iloc[: idx + 1],
            amount=market.amount.iloc[: idx + 1],
            source_mode=market.source_mode,
        )
        target = build_momentum_portfolio(sub_market.close, lookback=lookback, top_n=top_n, scheme="equal").holdings
        if target.empty:
            rows.append(
                {
                    "run_date": dates[idx].strftime("%Y-%m-%d"),
                    "status": "fail",
                    "signals": 0,
                    "orders": 0,
                    "pnl_rows": 0,
                }
            )
            continue
        exec_run = execute_rebalance(target, sub_market, initial_cash=1_000_000.0, lot_size=100)
        rows.append(
            {
                "run_date": dates[idx].strftime("%Y-%m-%d"),
                "status": "pass" if not exec_run.pnl.empty else "fail",
                "signals": len(target),
                "orders": len(exec_run.orders),
                "pnl_rows": len(exec_run.pnl),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    meta = ExperimentMeta(
        code="45",
        title="实盘收盘决策最小闭环",
        goal="验证收盘后数据装配、信号生成、建议单、执行、风控和调度是否能形成最小闭环。",
        root=ROOT,
    )

    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    raw_frames: list[pd.DataFrame] = []
    normalized_frames: list[pd.DataFrame] = []
    quality_issues: list[str] = []
    for phase, symbol in enumerate(SYMBOLS, start=1):
        raw = _make_raw_history(symbol, "2024-03-01", "2024-04-12", phase=phase)
        normalized = normalize_daily_history(raw, symbol)
        raw_frames.append(raw.assign(symbol=symbol))
        normalized_frames.append(normalized)
        issues = quality_checks(normalized)
        if issues:
            quality_issues.extend(f"{symbol}: {issue}" for issue in issues)

    raw_df = pd.concat(raw_frames, ignore_index=True)
    normalized_df = pd.concat(normalized_frames, ignore_index=True)
    market = _build_market_panel(normalized_frames)

    market_check = bool(
        list(market.close.index) == sorted(market.close.index.tolist())
        and set(market.close.columns) == set(SYMBOLS)
        and market.close.notna().all().all()
        and market.volume.notna().all().all()
        and market.amount.notna().all().all()
    )

    strategy_run = build_momentum_portfolio(market.close, lookback=5, top_n=2, scheme="equal")
    target = strategy_run.holdings
    backtest_run = execute_rebalance(target, market, initial_cash=1_000_000.0, lot_size=100)
    paper_run = execute_rebalance(
        target,
        market,
        initial_cash=1_000_000.0,
        lot_size=100,
        max_adv_pct=0.02,
        slippage_fn=dynamic_slippage_cost,
    )

    risk_equity = paper_run.pnl["equity"].copy()
    if len(risk_equity) >= 6:
        mid = len(risk_equity) // 2
        risk_equity.iloc[mid] *= 0.92
        if mid + 1 < len(risk_equity):
            risk_equity.iloc[mid + 1] *= 0.85
    risk_state = risk_state_machine(
        risk_equity,
        window=5,
        drawdown_warn=-0.01,
        drawdown_halt=-0.04,
        vol_warn=0.05,
        vol_halt=0.12,
    )
    latest_state = str(risk_state["state"].iloc[-1]) if not risk_state.empty else "normal"

    latest_date = market.close.index[-1]
    latest_target = target[pd.to_datetime(target["date"]) == latest_date].set_index("symbol")["weight"] if not target.empty else pd.Series(dtype=float)
    latest_prices = market.close.loc[latest_date]
    latest_volume = market.volume.loc[latest_date]
    latest_amount = market.amount.loc[latest_date]
    latest_volatility = market.close.pct_change().rolling(5, min_periods=1).std().loc[latest_date]

    target_shares = ((latest_target.reindex(latest_prices.index).fillna(0.0) * 1_000_000.0) / latest_prices).fillna(0.0)
    target_shares = np.floor(target_shares / 100.0) * 100.0
    current_positions = {
        latest_prices.index[0]: float(target_shares.iloc[0]),
        latest_prices.index[1]: 0.0,
        latest_prices.index[2]: float(target_shares.iloc[2] + 500.0),
    }
    gated_target_shares = target_shares.copy()
    if latest_state == "halt":
        gated_target_shares[:] = 0.0
    elif latest_state == "caution":
        gated_target_shares[:] = gated_target_shares * 0.5
    advice = _build_advice(
        gated_target_shares,
        current_positions,
        latest_prices,
        latest_amount,
        latest_volatility,
        latest_state,
    )

    schedule_log = _simulate_schedule(market, lookback=5, top_n=2, window_count=5)

    save_csv(raw_df, artifact_dir / "raw.csv")
    save_csv(normalized_df, artifact_dir / "normalized.csv")
    save_csv(
        pd.DataFrame(
            {
                "symbol": market.close.columns,
                "latest_close": latest_prices.values,
                "latest_volume": latest_volume.values,
                "latest_amount": latest_amount.values,
            }
        ),
        artifact_dir / "market_snapshot.csv",
    )
    save_csv(strategy_run.holdings, artifact_dir / "signals.csv")
    save_csv(backtest_run.orders, artifact_dir / "backtest_orders.csv")
    save_csv(backtest_run.pnl, artifact_dir / "backtest_pnl.csv")
    save_csv(paper_run.orders, artifact_dir / "paper_orders.csv")
    save_csv(paper_run.pnl, artifact_dir / "paper_pnl.csv")
    save_csv(risk_state.reset_index().rename(columns={"index": "date"}), artifact_dir / "risk_state.csv")
    save_csv(advice, artifact_dir / "advice.csv")
    save_csv(schedule_log, artifact_dir / "schedule_log.csv")

    a_ok = not quality_issues and market_check and market.source_mode == "lab-synthetic-close"
    b_ok = not strategy_run.holdings.empty and not advice.empty
    c_ok = {"买入", "卖出", "持有", "清仓"}.intersection(set(advice["action"]))
    d_ok = (
        not backtest_run.pnl.empty
        and not paper_run.pnl.empty
        and float(paper_run.pnl["slippage_cost"].sum()) > 0.0
        and float(paper_run.pnl["equity"].iloc[-1]) <= float(backtest_run.pnl["equity"].iloc[-1])
    )
    e_ok = bool((risk_state["state"] != "normal").any()) if not risk_state.empty else False
    f_ok = not schedule_log.empty and (schedule_log["status"] == "pass").all()
    overall_pass = a_ok and b_ok and c_ok and d_ok and e_ok and f_ok

    steps = [
        "用中文字段的原始日线样本做标准化和质量校验。",
        "把多标的日线样本装配成 MarketPanel，再跑单日动量信号和目标权重。",
        "把目标权重转成建议单，并用 backtest / paper 两种执行方式对比滑点影响。",
        "对权益曲线注入回撤冲击，验证风控状态机和建议单门控。",
        "按收盘后日级调度连续触发 5 次，检查任务可重复执行。",
    ]
    artifacts = [
        "artifacts/raw.csv",
        "artifacts/normalized.csv",
        "artifacts/market_snapshot.csv",
        "artifacts/signals.csv",
        "artifacts/backtest_orders.csv",
        "artifacts/backtest_pnl.csv",
        "artifacts/paper_orders.csv",
        "artifacts/paper_pnl.csv",
        "artifacts/risk_state.csv",
        "artifacts/advice.csv",
        "artifacts/schedule_log.csv",
    ]
    conclusion = "A-F 最小闭环已打通。" if overall_pass else "A-F 最小闭环存在未通过项。"
    record_experiment(meta, "pass" if overall_pass else "fail", steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
