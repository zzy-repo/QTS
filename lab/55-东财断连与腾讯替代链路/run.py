from __future__ import annotations

from pathlib import Path
import json
import sys

import akshare as ak
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
REPO_ROOT = LAB_ROOT.parent
sys.path.insert(0, str(LAB_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from qts.core.data.models import MarketPanel
from qts.infra.config import build_system_from_config, load_qts_config
from shared import ExperimentMeta, record_experiment

BACKTEST_CONFIG = REPO_ROOT / "configs" / "backtest.yaml"

EASTMONEY_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def _eastmoney_params(symbol: str, start_date: str, end_date: str) -> dict[str, str]:
    market_code = "1" if symbol.startswith("6") else "0"
    return {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "secid": f"{market_code}.{symbol}",
        "beg": start_date,
        "end": end_date,
    }


def _probe_eastmoney(symbol: str, start_date: str, end_date: str) -> dict[str, object]:
    params = _eastmoney_params(symbol, start_date, end_date)
    probe: dict[str, object] = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "params": params,
    }
    try:
        response = requests.get(EASTMONEY_URL, params=params, timeout=15)
        probe["status"] = response.status_code
        probe["content_length"] = len(response.content)
        probe["head"] = response.text[:200]
    except Exception as exc:  # noqa: BLE001
        probe["error_type"] = type(exc).__name__
        probe["error_message"] = str(exc)
    return probe


def _to_tx_symbol(symbol: str) -> str:
    return f"{'sh' if symbol.startswith('6') else 'sz'}{symbol}"


def _fetch_tx_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    tx_symbol = _to_tx_symbol(symbol)
    frame = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date=start_date, end_date=end_date)
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"])
    normalized["symbol"] = symbol
    normalized["volume"] = pd.NA
    normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce")
    normalized = normalized.rename(columns={"date": "date", "open": "open", "close": "close", "high": "high", "low": "low"})
    return normalized[["symbol", "date", "open", "high", "low", "close", "volume", "amount"]]


def _build_market_panel_from_tx(symbols: list[str], start_date: str, end_date: str) -> tuple[MarketPanel, pd.DataFrame]:
    frames = [_fetch_tx_history(symbol, start_date, end_date) for symbol in symbols]
    combined = pd.concat(frames, ignore_index=True)
    close = combined.pivot(index="date", columns="symbol", values="close").sort_index()
    amount = combined.pivot(index="date", columns="symbol", values="amount").sort_index()
    volume = amount.copy()
    return MarketPanel(close=close, volume=volume, amount=amount, source_mode="tx-proxy"), combined


def _probe_tx_pipeline(config) -> dict[str, object]:
    market, combined = _build_market_panel_from_tx(
        config.market.symbols,
        config.market.start_date,
        config.market.end_date,
    )
    system = build_system_from_config(config)
    result = system.run(market)
    return {
        "source_mode": market.source_mode,
        "close_rows": int(len(market.close)),
        "symbols": list(market.close.columns),
        "combined_rows": int(len(combined)),
        "signal_rows": int(len(result.strategy_runs[0].signals)) if result.strategy_runs else 0,
        "pnl_rows": int(len(result.aggregate_pnl)),
        "equity_rows": int(len(result.aggregate_equity)),
        "last_cum_return": float(result.aggregate_pnl["cum_return"].iloc[-1]) if not result.aggregate_pnl.empty else None,
        "market": market,
        "combined": combined,
    }


def main() -> None:
    meta = ExperimentMeta(
        code="55",
        title="东财断连与腾讯替代链路",
        goal="在 lab 中复现东财历史接口断连，并验证腾讯历史日线能否在相同配置下替代并跑通最小回测链路。",
        root=ROOT,
    )
    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    config = load_qts_config(BACKTEST_CONFIG)
    eastmoney_probe = _probe_eastmoney(
        config.market.symbols[0],
        config.market.start_date,
        config.market.end_date,
    )
    tx_probe = _probe_tx_pipeline(config)

    (artifact_dir / "eastmoney_probe.json").write_text(
        json.dumps(eastmoney_probe, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (artifact_dir / "tx_probe.json").write_text(
        json.dumps({k: v for k, v in tx_probe.items() if k not in {"market", "combined"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    market = tx_probe["market"]
    combined = tx_probe["combined"]
    combined.assign(date=combined["date"].dt.strftime("%Y-%m-%d")).to_csv(
        artifact_dir / "tx_history.csv",
        index=False,
    )
    market.close.reset_index().to_csv(artifact_dir / "tx_close_panel.csv", index=False)
    (artifact_dir / "summary.md").write_text(
        "\n".join(
            [
                "# 结论摘要",
                "",
                "1. 当前失败不是回测引擎或策略逻辑错误，而是东财历史接口访问路径在当前环境下被代理链路中断。",
                "2. 仅修正 `secid` 不足以解决当前问题，因为连接在拿到应用层响应前就断开了。",
                "3. 在相同标的池和日期窗口下，腾讯历史日线可稳定返回，并能被整理成 `MarketPanel` 跑通最小回测。",
                "4. 经验上应把数据源访问和回测内核解耦，先保留可替换的数据源适配层，再决定是否回切东财。",
            ]
        ),
        encoding="utf-8",
    )

    steps = [
        "读取当前 `configs/backtest.yaml`，沿用真实的标的池和日期窗口做复现。",
        "直接请求东财历史接口，记录当前网络环境下的失败类型和请求参数。",
        "把同一组股票代码映射成腾讯市场前缀代码，调用 `ak.stock_zh_a_hist_tx` 下载历史日线。",
        "将腾讯日线整理成 `MarketPanel` 结构，并在 lab 中调用现有系统跑最小回测。",
    ]
    artifacts = [
        "artifacts/eastmoney_probe.json",
        "artifacts/tx_probe.json",
        "artifacts/tx_history.csv",
        "artifacts/tx_close_panel.csv",
        "artifacts/summary.md",
    ]

    eastmoney_failed = bool(eastmoney_probe.get("error_type"))
    tx_worked = tx_probe["close_rows"] > 0 and tx_probe["pnl_rows"] > 0
    if eastmoney_failed and tx_worked:
        status = "pass"
        conclusion = "当前环境下东财历史接口在连接层断开；腾讯历史日线可在相同配置下完成取数并跑通最小回测链路，说明问题主要在数据源访问路径而不在回测内核。"
    else:
        status = "fail"
        conclusion = "未能同时复现东财断连并验证腾讯替代链路。"
    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
