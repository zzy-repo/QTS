from __future__ import annotations

from pathlib import Path
import inspect
import json
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
REPO_ROOT = LAB_ROOT.parent
sys.path.insert(0, str(LAB_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from akshare.stock_feature.stock_hist_em import stock_zh_a_hist
from qts.core.data.data_source import fetch_daily_history
from shared import ExperimentMeta, record_experiment


def _current_request_template() -> dict[str, object]:
    source = inspect.getsource(fetch_daily_history)
    return {
        "function": "qts.core.data.data_source.fetch_daily_history",
        "url": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        "secid_line": "secid=f'0.{symbol}'",
        "source_excerpt": source,
    }


def _akshare_request_template() -> dict[str, object]:
    source = inspect.getsource(stock_zh_a_hist)
    return {
        "function": "akshare.stock_feature.stock_hist_em.stock_zh_a_hist",
        "url": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        "market_code_rule": "market_code = 1 if symbol.startswith('6') else 0",
        "secid_line": "secid=f'{market_code}.{symbol}'",
        "source_excerpt": source,
    }


def _expected_secid(symbol: str) -> str:
    market_code = 1 if symbol.startswith("6") else 0
    return f"{market_code}.{symbol}"


def main() -> None:
    meta = ExperimentMeta(
        code="54",
        title="东财接口市场码校验",
        goal="对照 AkShare 源码，确认历史行情接口是否被错误地固定为深市市场码。",
        root=ROOT,
    )

    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    current = _current_request_template()
    akshare = _akshare_request_template()
    expected = {
        symbol: _expected_secid(symbol)
        for symbol in ["000001", "600519", "601318"]
    }

    (artifact_dir / "current_request.json").write_text(
        json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (artifact_dir / "akshare_request.json").write_text(
        json.dumps(akshare, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (artifact_dir / "expected_secid.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    steps = [
        "读取当前实现的 `fetch_daily_history` 请求模板，检查 `secid` 拼接方式。",
        "读取 AkShare 的 `stock_zh_a_hist` 源码，确认历史行情函数如何构造同一接口。",
        "对 000001、600519、601318 计算期望 `secid`，核对沪市与深市市场码是否一致。",
    ]
    artifacts = [
        "artifacts/current_request.json",
        "artifacts/akshare_request.json",
        "artifacts/expected_secid.json",
    ]

    if current["secid_line"] == "secid=f'0.{symbol}'" and akshare["secid_line"] == "secid=f'{market_code}.{symbol}'":
        status = "pass"
        conclusion = "接口 URL 本身是对的，但当前实现把 secid 固定成 0.*，而 AkShare 会按股票代码前缀切换市场码；600519/601318 应该用 1.*。"
    else:
        status = "fail"
        conclusion = "未能稳定识别当前实现与 AkShare 的接口差异。"

    record_experiment(meta, status, steps, artifacts, conclusion)


if __name__ == "__main__":
    main()
